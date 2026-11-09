"""Tidy extracts for Tableau / Qlik Sense (a small star schema) + a Qlik load script.

Build guide: docs/tableau-build-guide.md. Each extract is one grain, documented in
docs/data-dictionary.md, so a self-service user never has to guess what a row is.
"""
from __future__ import annotations

from pathlib import Path

EXTRACTS = {
    "dim_product": "SELECT product_code, fund_name, vehicle, asset_class, category, family_code, family_name, "
                   "mgmt_fee_bps FROM stg_products",
    "dim_advisor": "SELECT advisor_key, advisor_name, firm_id, firm_name, channel, channel_group, territory_code, "
                   "territory_name, region, tier, practice_focus, book_aum_est FROM stg_advisors",
    "dim_wholesaler": "SELECT wholesaler_id, wholesaler_name, role, territory_code, channel_group, start_month_key, "
                      "end_month_key FROM stg_wholesalers",
    "dim_month": "SELECT month_key, month_index, month_start, month_end, year_num, quarter_label, month_label FROM dim_month",
    "fact_product_month": "SELECT product_code, month_key, beginning_aum, gross_sales, redemptions, net_flows, "
                          "market_effect, ending_aum, revenue_run_rate, feed_gross, mapped_gross, excess_return "
                          "FROM mart_product_month",
    "fact_flows_channel_territory": "SELECT month_key, channel, territory_code, family_code, gross_sales, redemptions, "
                                    "net_flows, producing_advisors FROM mart_flows_channel_territory_month",
    "fact_wholesaler_month": "SELECT wholesaler_id, month_key, in_person_meetings, virtual_meetings, calls, emails, "
                             "advisors_touched, credited_gross_sales, monthly_goal FROM mart_wholesaler_month",
    "fact_kpi": "SELECT kpi_id, month_key, dim, value, target, rag FROM kpi_results",
    "kpi_definitions": "SELECT * FROM kpi_definitions",
    "nba_call_lists": "SELECT * FROM ml_nba_recommendations",
    "redemption_watchlist": "SELECT * FROM ml_redemption_watchlist",
}

QLIK = """// FlowSight - Qlik Sense load script (data load editor)
// Point the connection 'FlowSightExtracts' at the outputs/bi folder.
// Keys are named identically across tables so Qlik associates them automatically; Month is the
// shared calendar and no two tables share more than one field (no synthetic keys).

LIB CONNECT TO 'FlowSightExtracts';

[Month]:        LOAD * FROM [lib://FlowSightExtracts/dim_month.csv] (txt, utf8, embedded labels, delimiter is ',');
[Product]:      LOAD * FROM [lib://FlowSightExtracts/dim_product.csv] (txt, utf8, embedded labels, delimiter is ',');
[Wholesaler]:   LOAD wholesaler_id, wholesaler_name, role, territory_code AS wholesaler_territory, channel_group AS wholesaler_group
                FROM [lib://FlowSightExtracts/dim_wholesaler.csv] (txt, utf8, embedded labels, delimiter is ',');
[ProductMonth]: LOAD product_code, month_key, beginning_aum, gross_sales, redemptions, net_flows, market_effect,
                     ending_aum, revenue_run_rate, feed_gross, mapped_gross, excess_return
                FROM [lib://FlowSightExtracts/fact_product_month.csv] (txt, utf8, embedded labels, delimiter is ',');
[WholesalerMonth]: LOAD wholesaler_id, month_key, in_person_meetings, virtual_meetings, calls,
                     advisors_touched, credited_gross_sales, monthly_goal
                FROM [lib://FlowSightExtracts/fact_wholesaler_month.csv] (txt, utf8, embedded labels, delimiter is ',');
[KPI]:          LOAD kpi_id, month_key, dim AS kpi_dim, value AS kpi_value, target AS kpi_target, rag AS kpi_status
                FROM [lib://FlowSightExtracts/fact_kpi.csv] (txt, utf8, embedded labels, delimiter is ',');

// Master measures (create in the app; same definitions as config/kpis.yaml):
//   Net flows            = Sum(net_flows)
//   Organic growth (ann) = Sum(net_flows) * 12 / Sum(beginning_aum)
//   Redemption rate      = Sum(redemptions) * 12 / Sum(beginning_aum)
//   Feed coverage        = Sum(feed_gross) / Sum(gross_sales)
//   Goal attainment      = Sum(credited_gross_sales) / Sum(monthly_goal)
"""


def write_bi_extracts(engine, out_dir: Path) -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    counts = {}
    for name, sql in EXTRACTS.items():
        df = engine.query(sql)
        df.to_csv(out_dir / f"{name}.csv", index=False)
        counts[name] = len(df)
    (out_dir / "flowsight_load_script.qvs").write_text(QLIK, encoding="utf-8")
    return counts
