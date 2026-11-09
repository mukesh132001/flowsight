"""Monthly KPI commentary: the 'so what' a Head of Distribution reads first.

The bullets are computed from the scorecard, the net-flow driver analysis and the alert
log, with automatic root-cause hints for the alerts (e.g. which vendor and rep-code pattern
caused an attribution gap, or whether a territory's meeting drop lines up with a vacant
seat). An LLM can polish the wording; the guardrails reject any number it did not get.
"""
from __future__ import annotations

import json

import pandas as pd

from ..config import month_label
from .guardrails import FOOTER, review
from .llm import LLMClient

SYSTEM = """You are a distribution analytics lead writing the monthly commentary for the Head of \
Distribution at an asset manager. Rewrite the bullet facts you are given into an executive \
summary: a one-sentence headline, then 5-7 bullets (what happened, why, what to watch, what we \
are doing). Use only the numbers provided, keep their units, no forecasts or promises, \
max 180 words, markdown."""


def _m(x: float) -> str:
    x = float(x)
    sign = "+" if x > 0 else "-" if x < 0 else ""
    a = abs(x)
    if a >= 1e9:
        return f"{sign}${a / 1e9:,.2f}B"
    if a >= 1e6:
        return f"{sign}${a / 1e6:,.0f}M"
    return f"{sign}${a / 1e3:,.0f}K"


def _plain_m(x: float) -> str:
    return _m(x).lstrip("+")


def root_cause(engine, alert) -> str:
    """Drill into an alert and return a one-line hint (or '')."""
    if alert.kpi_id == "dq_unattributed_sales":
        df = engine.query("SELECT source_vendor, channel, rep_code, gross_sales FROM fct_trades "
                          f"WHERE is_mapped = 0 AND month_key = {alert.month_key}")
        if df.empty:
            return ""
        by = df.groupby(["source_vendor", "channel"]).gross_sales.sum().sort_values(ascending=False)
        (vendor, channel), top = by.index[0], by.iloc[0]
        share = top / df.gross_sales.sum()
        under = df.rep_code.str.contains("_", regex=False).mean()
        fmt = (f"; {under:.0%} of the unmapped rep codes use '_' where the crosswalk uses '-' "
               "(feed format change)") if under > 0.5 else ""
        return f"{share:.0%} of the unmapped dollars came from {channel} firms in vendor {vendor}'s feed{fmt}"
    if alert.kpi_id == "external_meetings_by_territory":
        seats = engine.query("SELECT month_key, COUNT(DISTINCT wholesaler_id) AS seats FROM mart_wholesaler_month "
                             f"WHERE role = 'External' AND territory_code = '{alert.dim}' GROUP BY month_key")
        s = dict(zip(seats.month_key, seats.seats))
        prior = [k for k in sorted(s) if k < alert.month_key][-12:]
        planned = max((s[k] for k in prior), default=0)
        now = s.get(alert.month_key, 0)
        if prior and now < planned:
            gap = [k for k in sorted(s) if k <= alert.month_key and s[k] < planned]
            start = [k for k in gap if all(s[j] < planned for j in sorted(s) if k <= j <= alert.month_key)][0]
            filled = sorted(k for k in s if k > alert.month_key and s[k] >= planned)
            back = f", refilled {month_label(filled[0])}" if filled else ", still open"
            return (f"only {now} of {planned} external seats in {alert.dim} filled since "
                    f"{month_label(start)}{back}")
        return ""
    return ""


def build_facts(engine, card: pd.DataFrame, drivers: dict, alerts: pd.DataFrame, ml: dict | None) -> dict:
    c = card.set_index("kpi_id")
    as_of = int(drivers["as_of"])
    t, tp = drivers["totals"], drivers["totals_prior"]

    def v(k):
        return c.loc[k, "value"] if k in c.index else None

    bullets = []
    nf, plan = v("net_flows"), c.loc["net_flows", "target"]
    bullets.append(f"Net flows were {_m(nf)} in {month_label(as_of)} (prior month {_m(tp['net_flows'])}), "
                   f"{nf / plan:.0%} of plan; organic growth ran at {v('organic_growth_rate'):.1%} annualised "
                   f"against a 4.0% target.")
    bullets.append(f"Gross sales {_plain_m(t['gross_sales'])} and redemptions {_plain_m(t['redemptions'])}; "
                   f"the redemption rate was {v('redemption_rate'):.1%} ({c.loc['redemption_rate', 'rag'].lower()}).")
    aum_chg = t["net_flows"] + t["market_effect"]
    bullets.append(f"AUM ended at {_plain_m(v('ending_aum'))} ({_m(aum_chg)} in the month: markets "
                   f"{_m(t['market_effect'])}, net flows {_m(t['net_flows'])}); YTD net flows "
                   f"{_m(drivers['ytd_net_flows'])}.")
    fm = drivers["family_mom"]
    ups = [f"{k} {_m(x)}" for k, x in list(fm["top_up"].items())[:2]]
    downs = [f"{k} {_m(x)}" for k, x in list(fm["top_down"].items())[:2]]
    if ups or downs:
        bullets.append("Biggest swings in net flows vs last month: " + ", ".join(ups + downs) + ".")
    reds = card[(card.rag == "RED")]
    if len(reds):
        bullets.append("Off track: " + "; ".join(
            f"{r.name} at {_fmt(r.value, r.unit)} vs target {_fmt(r.target, r.unit)}" for r in reds.itertuples()) + ".")
    recent = alerts[alerts.month_key >= sorted(alerts.month_key.unique())[-3]] if len(alerts) else alerts
    recent = recent.sort_values("month_key", ascending=False).drop_duplicates(["kpi_id", "dim"])
    watch = []
    for a in recent.itertuples():
        if a.direction != "adverse" or a.kpi_id == "net_flows_by_family":
            continue
        hint = root_cause(engine, a)
        dim = "" if a.dim == "ALL" else f" ({a.dim})"
        watch.append(f"{a.kpi_name}{dim} moved to {_fmt(a.value, _unit(a.kpi_id, card))} in "
                     f"{month_label(a.month_key)} vs a trailing median of {_fmt(a.trailing_median, _unit(a.kpi_id, card))}"
                     + (f" - {hint}" if hint else ""))
    if watch:
        bullets.append("Watch: " + "; ".join(watch[:3]) + ".")
    if ml:
        flow = [p for p in ml["policy"] if p["policy"].startswith("FlowSight")][0]
        bullets.append(f"Next-best-action call lists are ready for {flow['wholesalers']} external wholesalers; in the "
                       f"simulated test they added {flow['vs_rule']:+.0%} more incremental sales than a "
                       f"largest-books rule with the same number of meetings.")
    return {"as_of": month_label(as_of), "bullets": bullets,
            "headline_kpis": {k: (None if pd.isna(v(k)) else float(v(k))) for k in c.index}}


def _unit(kid: str, card: pd.DataFrame) -> str:
    if kid in set(card.kpi_id):
        return card.set_index("kpi_id").loc[kid, "unit"]
    return "count" if "meetings" in kid else "usd"


def _fmt(x, unit):
    if x is None or pd.isna(x):
        return "n/a"
    if unit == "pct":
        return f"{x:.1%}"
    if unit == "usd":
        return _plain_m(x)
    return f"{x:,.1f}" if abs(x) < 100 else f"{x:,.0f}"


def write_commentary(engine, card, drivers, alerts, ml, client: LLMClient, out_dir) -> dict:
    facts = build_facts(engine, card, drivers, alerts, ml)
    text, provider, issues = None, "template", []
    if client.online:
        draft = client.complete(SYSTEM, json.dumps({"month": facts["as_of"], "facts": facts["bullets"]}, indent=1))
        if draft:
            check = review(draft + "\n" + FOOTER, facts)
            if check.ok:
                text, provider = draft, f"llm:{client.model}"
            else:
                issues = check.issues
    if text is None:
        text = (f"**{facts['as_of']} distribution commentary**\n\n"
                + "\n".join(f"- {b}" for b in facts["bullets"]))
    text = text.rstrip() + f"\n\n*{FOOTER}*\n"
    final = review(text, facts)
    (out_dir / "commentary.md").write_text(text, encoding="utf-8")
    payload = {**facts, "provider": provider, "guardrail_ok": final.ok,
               "guardrail_issues": issues + final.issues, "text": text}
    (out_dir / "commentary.json").write_text(json.dumps(payload, indent=1, default=float))
    return payload
