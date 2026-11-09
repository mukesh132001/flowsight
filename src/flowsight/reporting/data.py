"""Assemble one report model (plain dicts / lists) shared by the Excel pack, the PowerPoint
deck and the web dashboard, so all three always show the same numbers."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from ..config import month_label
from ..simulate.catalog import FIRM_NAME


def _f(x):
    if x is None:
        return None
    if isinstance(x, (np.floating, float)):
        return None if np.isnan(x) else float(x)
    if isinstance(x, (np.integer,)):
        return int(x)
    return x


def _records(df: pd.DataFrame) -> list[dict]:
    return [{k: _f(v) for k, v in r.items()} for r in df.to_dict(orient="records")]


def build_report_model(engine, out_dir: Path, as_of: int) -> dict:
    out_dir = Path(out_dir)
    card = pd.read_json(out_dir / "kpi_scorecard.json")
    drivers = json.loads((out_dir / "net_flow_drivers.json").read_text())
    commentary = json.loads((out_dir / "commentary.json").read_text())
    ml = json.loads((out_dir / "ml_metrics.json").read_text())
    alerts = engine.table("kpi_alerts")
    results = engine.table("kpi_results")

    pm = engine.query("SELECT * FROM mart_product_month")
    months = sorted(pm.month_key.unique())
    labels = {m: month_label(int(m)) for m in months}
    tot = pm.groupby("month_key")[["beginning_aum", "gross_sales", "redemptions", "net_flows",
                                   "market_effect", "ending_aum", "revenue_run_rate"]].sum()
    plan = results[(results.kpi_id == "net_flows")].set_index("month_key")["target"]
    monthly = [{"month_key": int(m), "month": labels[m], "gross_sales": float(r.gross_sales),
                "redemptions": float(r.redemptions), "net_flows": float(r.net_flows),
                "plan_net_flows": _f(plan.get(m)), "market_effect": float(r.market_effect),
                "ending_aum": float(r.ending_aum), "revenue_run_rate": float(r.revenue_run_rate),
                "organic_growth": float(r.net_flows * 12 / r.beginning_aum) if r.beginning_aum else None}
               for m, r in tot.iterrows()]

    year = as_of // 100
    ytd = tot[(tot.index // 100 == year) & (tot.index <= as_of)]
    start_aum = float(ytd.beginning_aum.iloc[0])
    bridge_ytd = [{"step": f"AUM {month_label(int(ytd.index[0]) - 1 if ytd.index[0] % 100 > 1 else (year - 1) * 100 + 12)}",
                   "value": start_aum, "kind": "total"},
                  {"step": "Gross sales", "value": float(ytd.gross_sales.sum()), "kind": "up"},
                  {"step": "Redemptions", "value": -float(ytd.redemptions.sum()), "kind": "down"},
                  {"step": "Market & FX", "value": float(ytd.market_effect.sum()),
                   "kind": "up" if ytd.market_effect.sum() >= 0 else "down"},
                  {"step": f"AUM {month_label(as_of)}", "value": float(ytd.ending_aum.iloc[-1]), "kind": "total"}]

    fam = pm[(pm.month_key // 100 == year) & (pm.month_key <= as_of)].groupby("family_name")[
        ["gross_sales", "redemptions", "net_flows"]].sum()
    fam_aum = pm[pm.month_key == as_of].groupby("family_name").ending_aum.sum()
    families = [{"family": k, "gross_sales": float(r.gross_sales), "redemptions": float(r.redemptions),
                 "net_flows_ytd": float(r.net_flows), "aum": float(fam_aum.get(k, 0))}
                for k, r in fam.sort_values("net_flows", ascending=False).iterrows()]

    last12 = months[-12:]
    funds = []
    ex3 = pm[pm.month_key.isin(months[-3:])].groupby("product_code").excess_return.sum()
    for code, g in pm[pm.month_key.isin(last12)].groupby("product_code"):
        cur = g[g.month_key == as_of].iloc[0]
        beg = g.sort_values("month_key").iloc[0].beginning_aum
        nf12 = g.net_flows.sum()
        funds.append({"product_code": code, "fund": cur.fund_name, "family": cur.family_name,
                      "vehicle": cur.vehicle, "aum": float(cur.ending_aum), "net_flows_12m": float(nf12),
                      "organic_growth_12m": float(nf12 / beg) if beg and beg >= 1e8 else None,  # n/m for new launches
                      "excess_3m": _f(ex3.get(code))})
    funds.sort(key=lambda x: -x["aum"])

    ct = engine.query("SELECT month_key, territory_code, SUM(net_flows) AS net_flows FROM "
                      "mart_flows_channel_territory_month GROUP BY month_key, territory_code")
    terr_names = engine.query("SELECT DISTINCT territory_code, territory_name FROM stg_territories")
    tn = dict(zip(terr_names.territory_code, terr_names.territory_name))
    tn["UNATTRIBUTED"] = "Unattributed"
    heat = ct[ct.month_key.isin(last12)]
    heat_rows = [{"territory": tn.get(t, t), "code": t,
                  "values": [float(heat[(heat.territory_code == t) & (heat.month_key == m)].net_flows.sum())
                             for m in last12]}
                 for t in sorted(heat.territory_code.unique(), key=lambda x: (x == "UNATTRIBUTED", tn.get(x, x)))]
    channel = engine.query("SELECT channel, SUM(net_flows) AS net_flows, SUM(gross_sales) AS gross_sales FROM "
                           f"mart_flows_channel_territory_month WHERE month_key / 100 = {year} AND month_key <= {as_of} "
                           "GROUP BY channel ORDER BY gross_sales DESC")

    q = f"{year}Q{(as_of % 100 - 1) // 3 + 1}"
    wm = engine.query(f"SELECT * FROM mart_wholesaler_month WHERE quarter_label = '{q}'")
    conv = engine.query("SELECT wholesaler_id, AVG(CAST(converted_3m AS DOUBLE)) AS conversion, COUNT(*) AS n "
                        "FROM mart_activity_conversion WHERE activity_type <> 'Call' "
                        f"AND month_index BETWEEN (SELECT MAX(month_index) - 7 FROM dim_month) "
                        f"AND (SELECT MAX(month_index) - 2 FROM dim_month) GROUP BY wholesaler_id")
    ws = (wm.groupby(["wholesaler_id", "wholesaler_name", "role", "territory_code", "channel_group"])
            .agg(meetings=("in_person_meetings", "sum"), virtual=("virtual_meetings", "sum"),
                 calls=("calls", "sum"), advisors_touched=("advisors_touched", "sum"),
                 credited_gross=("credited_gross_sales", "sum"), goal=("monthly_goal", "sum"),
                 months=("month_key", "nunique")).reset_index())
    ws["meetings"] = ws["meetings"] + ws["virtual"]
    ws = ws.merge(conv, on="wholesaler_id", how="left")
    ws["attainment"] = ws.credited_gross / ws.goal.replace(0, np.nan)
    ws["territory"] = ws.territory_code.map(tn)
    ws = ws.sort_values(["role", "attainment"], ascending=[True, False])

    recs = engine.table("ml_nba_recommendations")
    briefs = engine.table("ai_briefs") if "ai_briefs" in engine.tables() else pd.DataFrame()
    brief_text = {}
    if len(briefs):
        for b in briefs.itertuples():
            p = out_dir / "briefs" / b.file
            if p.exists():
                brief_text[(b.wholesaler_id, b.advisor_key, b.family_code)] = p.read_text(encoding="utf-8")
    recs["brief"] = [brief_text.get((r.wholesaler_id, r.advisor_key, r.family_code)) for r in recs.itertuples()]
    watch = engine.table("ml_redemption_watchlist")
    dq = engine.table("dq_results")
    unattr = results[(results.kpi_id == "dq_unattributed_sales")].sort_values("month_key")
    policy = pd.DataFrame(ml["policy"])

    return {
        "firm": FIRM_NAME, "as_of": int(as_of), "as_of_label": month_label(as_of), "quarter": q,
        "scorecard": _records(card),
        "commentary": commentary["bullets"], "commentary_provider": commentary["provider"],
        "monthly": monthly, "bridge_ytd": bridge_ytd, "families": families, "funds": funds,
        "heatmap": {"months": [labels[m] for m in last12], "rows": heat_rows},
        "channels": _records(channel),
        "wholesalers": _records(ws.drop(columns=["virtual"])),
        "recommendations": _records(recs),
        "watchlist": _records(watch.head(60)),
        "alerts": _records(alerts.assign(month=alerts.month_key.map(lambda m: month_label(int(m))))),
        "dq": _records(dq),
        "unattributed": [{"month": month_label(int(r.month_key)), "value": float(r.value)} for r in unattr.itertuples()],
        "policy": _records(policy),
        "ml": {"nba": ml["nba"], "attrition": ml["attrition"], "meeting_effect": ml["meeting_effect"],
               "months": ml["months"]},
        "drivers": drivers,
    }
