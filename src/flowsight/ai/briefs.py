"""Call-prep briefs for wholesalers, grounded in warehouse facts.

For each top recommendation the facts are gathered with SQL (holdings, recent meetings,
digital signals, 12-month flows, funds on the firm's shelf, model scores). The brief is
written by the LLM when a key is configured - and must then pass the guardrails - or by a
deterministic template otherwise. Either way only facts from the warehouse appear.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd

from ..config import month_label
from .guardrails import FOOTER, review
from .llm import LLMClient

SYSTEM = """You write internal call-prep notes for an asset manager's wholesalers (sales people who \
meet financial advisors). Use ONLY the facts in the JSON you are given. Never invent numbers, \
funds, people or events. Do not predict or promise performance; mention past performance only as \
given, and say that past performance does not guarantee future results if you mention it. \
Write in plain, confident business English, max 220 words, using exactly these markdown \
sections: '**Why now**', '**What to bring**', '**Talking points**' (3 bullets), \
'**Questions to ask**' (2 bullets), '**Next step**'. No preamble."""


def _money(x: float) -> str:
    x = float(x)
    if abs(x) >= 1e9:
        return f"${x / 1e9:,.1f}B"
    if abs(x) >= 1e6:
        return f"${x / 1e6:,.1f}M"
    if abs(x) >= 1e3:
        return f"${x / 1e3:,.0f}K"
    return f"${x:,.0f}"


def _in(keys) -> str:
    return "(" + ", ".join(f"'{k}'" for k in sorted(set(keys))) + ")"


def gather_facts(engine, recs: pd.DataFrame, as_of: int) -> list[dict]:
    keys = _in(recs.advisor_key)
    lo12 = as_of - 100
    pos = engine.query("SELECT p.advisor_key, pr.family_name, SUM(p.market_value) AS mv FROM fct_positions p "
                       "JOIN stg_products pr ON p.product_code = pr.product_code "
                       f"WHERE p.month_key = {as_of} AND p.advisor_key IN {keys} "
                       "GROUP BY p.advisor_key, pr.family_name")
    acts = engine.query("SELECT a.advisor_key, a.activity_date, a.activity_type, w.wholesaler_name, f.family_code "
                        "FROM stg_activities a JOIN stg_wholesalers w ON a.wholesaler_id = w.wholesaler_id "
                        "LEFT JOIN fct_activity_families f ON a.activity_id = f.activity_id "
                        f"WHERE a.is_completed = 1 AND a.activity_type <> 'Email' AND a.month_key <= {as_of} "
                        f"AND a.advisor_key IN {keys}")
    web = engine.query("SELECT e.advisor_key, e.event_date, e.event_type, p.fund_name FROM fct_web_events e "
                       "LEFT JOIN stg_products p ON e.product_code = p.product_code "
                       f"WHERE e.month_key > {as_of - 3 if as_of % 100 > 3 else as_of - 91} "
                       f"AND e.month_key <= {as_of} AND e.advisor_key IN {keys} AND e.event_type <> 'site_visit'")
    flows = engine.query("SELECT advisor_key, SUM(gross_sales) AS gross, SUM(redemptions) AS red FROM fct_trades "
                         f"WHERE is_mapped = 1 AND month_key > {lo12} AND month_key <= {as_of} "
                         f"AND advisor_key IN {keys} GROUP BY advisor_key")
    shelf = engine.query("SELECT a.advisor_key, p.family_code, p.fund_name, p.vehicle, p.mgmt_fee_bps "
                         "FROM int_advisor_firm_month a JOIN stg_shelf s ON a.firm_id = s.firm_id "
                         "JOIN stg_products p ON s.product_code = p.product_code "
                         f"WHERE a.month_key = {as_of} AND s.approved_month_key <= {as_of} "
                         f"AND (p.launch_month_key IS NULL OR p.launch_month_key <= {as_of}) AND a.advisor_key IN {keys}")
    perf = engine.query("SELECT fund_name, SUM(excess_return) AS excess_3m FROM mart_product_month "
                        f"WHERE month_key > {as_of - 3 if as_of % 100 > 3 else as_of - 91} AND month_key <= {as_of} "
                        "GROUP BY fund_name")
    perf_map = dict(zip(perf.fund_name, perf.excess_3m))
    fam_name = engine.query("SELECT DISTINCT family_code, family_name FROM stg_products")
    fam_name = dict(zip(fam_name.family_code, fam_name.family_name))

    facts = []
    for r in recs.itertuples():
        a = acts[acts.advisor_key == r.advisor_key].sort_values("activity_date", ascending=False)
        recent = []
        for (d, t, wn), g in a.groupby(["activity_date", "activity_type", "wholesaler_name"], sort=False):
            fams = sorted({fam_name.get(f, f) for f in g.family_code.dropna()})
            recent.append({"date": d, "type": t, "with": wn, "topics": fams})
        recent = sorted(recent, key=lambda x: x["date"], reverse=True)[:3]
        h = pos[pos.advisor_key == r.advisor_key].sort_values("mv", ascending=False)
        w = web[web.advisor_key == r.advisor_key].sort_values("event_date", ascending=False).head(4)
        f = flows[flows.advisor_key == r.advisor_key]
        sh = shelf[(shelf.advisor_key == r.advisor_key) & (shelf.family_code == r.family_code)]
        facts.append({
            "as_of": month_label(as_of),
            "wholesaler": r.wholesaler_name,
            "advisor": {"name": r.advisor_name, "firm": r.firm_name, "channel": r.channel,
                        "territory": r.territory_code, "tier": r.tier, "practice_focus": r.practice_focus,
                        "book_size": _money(r.book_aum_est)},
            "relationship": {
                "assets_with_us": _money(h.mv.sum()) if len(h) else "$0",
                "holdings_by_family": {x.family_name: _money(x.mv) for x in h.itertuples()},
                "gross_purchases_12m": _money(f.gross.iloc[0]) if len(f) else "$0",
                "redemptions_12m": _money(f.red.iloc[0]) if len(f) else "$0",
                "recent_meetings_and_calls": recent,
            },
            "digital_signals_3m": [{"date": x.event_date, "event": x.event_type.replace("_", " "),
                                    "fund": x.fund_name} for x in w.itertuples()],
            "recommendation": {
                "family": r.family_name,
                "funds_on_platform": [{"fund": x.fund_name, "vehicle": x.vehicle,
                                       "mgmt_fee_bps": int(x.mgmt_fee_bps),
                                       "excess_return_vs_category_3m": f"{perf_map.get(x.fund_name, 0):+.1%}"}
                                      for x in sh.itertuples()],
                "why": r.reasons.split(" | "),
            },
            "model": {"purchase_probability_without_meeting": f"{r.p_if_not_met:.0%}",
                      "purchase_probability_with_meeting": f"{r.p_if_met:.0%}",
                      "expected_incremental_gross_sales": _money(r.exp_value),
                      "rank_in_call_list": int(r.rank)},
        })
    return facts


def render_template(f: dict) -> str:
    a, rel, rec, m = f["advisor"], f["relationship"], f["recommendation"], f["model"]
    funds = rec["funds_on_platform"]
    fund_txt = "; ".join(f"{x['fund']} ({x['vehicle']}, {x['mgmt_fee_bps']} bps)" for x in funds) or "see platform list"
    lines = [f"### {a['name']} - {a['firm']}",
             f"*{a['channel']} · {a['territory']} · Tier {a['tier']} · {a['practice_focus']} · book {a['book_size']}*",
             "", "**Why now**"]
    lines += [f"- {w}" for w in rec["why"]]
    lines += ["", "**What to bring**", f"- {rec['family']}: {fund_txt}"]
    perf_bits = [f"{x['fund']} {x['excess_return_vs_category_3m']} vs category over 3 months" for x in funds]
    held = rel["holdings_by_family"]
    lines += ["", "**Talking points**"]
    if held:
        top = ", ".join(f"{k} ({v})" for k, v in list(held.items())[:3])
        lines.append(f"- Thank them for the existing relationship: {rel['assets_with_us']} with us across {top}.")
    else:
        lines.append("- New relationship: no assets with us yet, so lead with how the strategy fits their practice.")
    lines.append(f"- Tie {rec['family']} to a {a['practice_focus'].lower()} practice and the client conversations it supports.")
    if perf_bits:
        lines.append(f"- Recent relative results: {'; '.join(perf_bits[:2])}. Past performance does not guarantee future results.")
    fam_funds = {x["fund"] for x in funds}
    sig = [d for d in f["digital_signals_3m"] if d["fund"] in fam_funds]
    if sig:
        d = sig[0]
        lines.append(f"- Follow up on their {d['event']} ({d['fund']}, {d['date']}).")
    lines += ["", "**Questions to ask**",
              f"- Where does {rec['family'].lower()} sit in your models today, and what would make you add or replace a manager?",
              "- Which client situations are you solving for this quarter?"]
    if rel["recent_meetings_and_calls"]:
        last = rel["recent_meetings_and_calls"][0]
        lines += ["", f"**Last touch:** {last['type']} with {last['with']} on {last['date']}"
                  + (f" ({', '.join(last['topics'])})" if last["topics"] else "") + "."]
    lines += ["", "**Next step**",
              f"- Book the meeting this month (call-list rank #{m['rank_in_call_list']}). Model estimate: purchase "
              f"probability {m['purchase_probability_without_meeting']} without a meeting vs "
              f"{m['purchase_probability_with_meeting']} with one; expected incremental gross sales "
              f"{m['expected_incremental_gross_sales']}."]
    return "\n".join(lines)


def write_briefs(engine, recs: pd.DataFrame, as_of: int, out_dir: Path, client: LLMClient,
                 per_wholesaler: int = 2, max_briefs: int = 40) -> pd.DataFrame:
    top = (recs.sort_values(["wholesaler_id", "rank"]).groupby("wholesaler_id").head(per_wholesaler)
               .head(max_briefs))
    facts = gather_facts(engine, top, as_of)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for r, f in zip(top.itertuples(), facts):
        body, provider, issues = None, "template", []
        if client.online:
            body = client.complete(SYSTEM, json.dumps(f, indent=1))
            if body:
                head = (f"### {f['advisor']['name']} - {f['advisor']['firm']}\n"
                        f"*{f['advisor']['channel']} · {f['advisor']['territory']} · Tier {f['advisor']['tier']} · "
                        f"book {f['advisor']['book_size']}*\n\n")
                body = head + body
                check = review(body + "\n" + FOOTER, f)
                if check.ok:
                    provider = f"llm:{client.model}"
                else:
                    issues, body = check.issues, None
        if body is None:
            body = render_template(f)
        text = (f"{body}\n\n---\n*Prepared by FlowSight for {f['wholesaler']} · data as of {f['as_of']} · "
                f"generated {date.today().isoformat()}*\n*{FOOTER}*\n")
        final = review(text, f)
        name = f"{r.wholesaler_id}_{r.advisor_key}_{r.family_code}.md"
        (out_dir / name).write_text(text, encoding="utf-8")
        rows.append({"wholesaler_id": r.wholesaler_id, "wholesaler_name": r.wholesaler_name,
                     "advisor_key": r.advisor_key, "advisor_name": r.advisor_name, "family_code": r.family_code,
                     "rank": int(r.rank), "file": name, "provider": provider, "guardrail_ok": int(final.ok),
                     "guardrail_issues": "; ".join(issues + final.issues), "facts_json": json.dumps(f)})
    return pd.DataFrame(rows)
