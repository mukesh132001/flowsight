# Data lineage

Every table is built by a SQL file in [`models/`](../models). The runner discovers dependencies from the
`FROM` / `JOIN` clauses, so this picture is the same graph the code executes.

```mermaid
flowchart LR
    subgraph Bronze["Bronze: raw files, all text"]
        CRM[crm_activities<br/>crm_activity_products]
        VA[sales_vendor_a]
        VB[sales_vendor_b]
        XR[rep_code_xref<br/>advisor_master]
        POS[positions_monthly]
        TA[ta_fund_flows]
        WEB[web_engagement]
        REF[products · share classes · firms<br/>shelf · territories · wholesalers<br/>goals · returns · industry · RFPs]
    end
    subgraph Silver["Silver: cleaned, typed, conformed"]
        STA[stg_trades_vendor_a] --> FT[fct_trades]
        STB[stg_trades_vendor_b] --> FT
        SXR[stg_rep_xref] --> FT
        SACT[stg_activities] --> FAF[fct_activity_families]
        SADV[stg_advisors]
        FPOS[fct_positions]
        FWEB[fct_web_events]
        STAF[stg_ta_flows]
    end
    subgraph Gold["Gold: business marts"]
        PM[mart_product_month<br/>AUM bridge]
        CT[mart_flows_channel_territory_month]
        AM[mart_advisor_month]
        WM[mart_wholesaler_month]
        AC[mart_activity_conversion]
        MS[mart_market_share]
        IP[mart_inst_pipeline]
    end
    subgraph Features
        FF[feat_advisor_family_month]
        FA[feat_advisor_month]
    end
    VA --> STA
    VB --> STB
    XR --> SXR
    XR --> SADV
    CRM --> SACT
    POS --> FPOS
    WEB --> FWEB
    TA --> STAF
    FT --> PM & CT & AM & WM & AC
    STAF --> PM
    FAF --> AC & FF
    FPOS --> AM & FF
    FWEB --> AM & FF
    AM --> FA
    PM --> FF & FA & MS
    Gold --> KPI[kpi_results<br/>kpi_alerts<br/>kpi_scorecard]
    Features --> ML[ml_nba_recommendations<br/>ml_redemption_watchlist]
    KPI --> OUT[Excel pack · PowerPoint · dashboard<br/>BI extracts · commentary]
    ML --> OUT
    ML --> AI[call-prep briefs]
```

## Layers

| Layer | Rule | Tables |
| --- | --- | --- |
| Bronze | Exactly as received, every column text, plus `_source_file` / `_ingested_at` | 20 `raw_*` tables + `load_audit` |
| Silver | One row per real-world thing; types parsed; duplicates removed; keys mapped; nothing aggregated | 20 `stg_*` / `fct_*` tables |
| Gold | Business grain (fund-month, advisor-month, wholesaler-month...), the only layer reports read | 8 `mart_*` / `int_*` tables |
| Features | Model inputs with point-in-time windows; `y_*` / `t_*` columns look forward and are labels only | 2 `feat_*` tables |
| Serving | KPI results, alerts, call lists, watchlist, briefs, report files | `kpi_*`, `ml_*`, `ai_*`, `outputs/` |

## Keys that hold it together

* `rep_code` -> `advisor_key` through `stg_rep_xref`, **valid for the trade month** (advisors change codes when
  they move firms; split / joint codes missing from the crosswalk stay in as unmapped).
* `share_class_code` -> `product_code` (vendor B) and firm *name* -> `firm_id` (vendor B).
* `crm_contact_id` (CRM) and `email_hash` (marketing) -> `advisor_key`.
* `month_key` (yyyymm) everywhere, with `dim_month.month_index` for window arithmetic - no date functions,
  which is what keeps the SQL portable between SQLite and Spark.

## Controls along the way

Control totals at load (rows and dollars), uniqueness and mapping checks in silver, reconciliation to the
transfer agent in gold, and the column-documentation test on every table - see the
[data dictionary](data-dictionary.md) and `models/checks/`.
