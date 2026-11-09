# Tableau / Qlik Sense build guide

`python -m flowsight run` writes a small star schema to `outputs/bi/` (CSV). This guide builds a three-page
Tableau Public workbook from it in about an hour; the same extracts load into Qlik Sense with the script in
`outputs/bi/flowsight_load_script.qvs`.

## 1. Data source (Tableau)

1. **Connect -> Text file** -> `fact_product_month.csv`. Add, as **relationships** (not joins):
   * `dim_product` on `product_code`
   * `dim_month` on `month_key`
2. New data source: `fact_wholesaler_month` related to `dim_wholesaler` (`wholesaler_id`) and `dim_month`.
3. New data source: `fact_flows_channel_territory` related to `dim_month`.
4. New data source: `fact_kpi` related to `kpi_definitions` (`kpi_id`).
5. Set `month_start` (dim_month) to a **Date** type; set `mgmt_fee_bps` and the money columns to numbers.

## 2. Calculated fields (same definitions as `config/kpis.yaml`)

```text
Net Flows            = SUM([Gross Sales]) - SUM([Redemptions])
Organic Growth (ann) = SUM([Net Flows]) * 12 / SUM([Beginning Aum])
Redemption Rate (ann)= SUM([Redemptions]) * 12 / SUM([Beginning Aum])
Feed Coverage        = SUM([Feed Gross]) / SUM([Gross Sales])
Attribution Gap $    = SUM([Feed Gross]) - SUM([Mapped Gross])
Fee Run Rate         = SUM([Ending Aum] * [Mgmt Fee Bps] / 10000)
Goal Attainment      = SUM([Credited Gross Sales]) / SUM([Monthly Goal])
Meetings             = SUM([In Person Meetings]) + SUM([Virtual Meetings])
Latest Month?        = [Month Key] = { FIXED : MAX([Month Key]) }        // LOD for "current month" tiles
Prior Month Net Flows= LOOKUP([Net Flows], -1)                            // table calc along month_start
Status               = IF [Organic Growth (ann)] >= 0.04 THEN "On track"
                       ELSEIF [Organic Growth (ann)] >= 0 THEN "Watch" ELSE "Off track" END
```

## 3. Sheets and dashboards

| Dashboard | Sheets | Build notes |
| --- | --- | --- |
| **Executive overview** | KPI tiles (Net Flows, Organic Growth, AUM, Redemption Rate for the latest month); Net flows by month (bars, colour = sign of Net Flows: blue in, red out) with a reference line at plan; AUM bridge (Gantt-bar waterfall: running sum of steps) | Filter tiles with `Latest Month? = True`; one filter row (date range) at the top drives every sheet |
| **Products & territories** | Net flows by family (ranked horizontal bars); territory x month highlight table (diverging blue-gray-red, centre 0); fund table with 12-month net flows and 3-month excess return | Use the diverging palette with the centre at 0 so gray means "about flat" |
| **Sales team** | Wholesaler scorecard (text table + bullet chart: Credited Gross vs Monthly Goal); meetings by territory over time | Bullet chart: Credited Gross as bar, goal as reference line per cell |

Design rules carried over from the web dashboard: one axis per chart (no dual axes), thin bars, hairline
gridlines, labels in gray ink (not series colours), status always shown with a word, and a "view data" option
on every chart.

## 4. Publish

File -> Save to Tableau Public. Link the workbook from the README next to the GitHub Pages dashboard.

## Qlik Sense

1. Create a folder connection named `FlowSightExtracts` pointing at `outputs/bi`.
2. Paste `flowsight_load_script.qvs` into the data load editor and load.
3. Create master measures from the comments at the bottom of the script (same formulas as above), then build
   the same three sheets. Qlik associates the tables on the shared key names (`product_code`, `month_key`,
   `wholesaler_id`).
