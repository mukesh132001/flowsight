# KPI dictionary

_Generated from `config/kpis.yaml` by `python -m flowsight docs` - edit the YAML, not this file._

| Tier | KPI | Definition | Formula | Target | Status rule | Owner |
| --- | --- | --- | --- | --- | --- | --- |
| north star | **Organic growth rate (annualised)** (`organic_growth_rate`) | Net flows as a share of beginning AUM, annualised. Separates growth we earned from growth the market gave us. | 12 x SUM(net flows) / SUM(beginning AUM) | 4.0% | green >= 4.0%, amber >= 0.0% | Head of Distribution |
| driver | **Net flows** (`net_flows`) | Gross sales minus redemptions across all funds, from transfer-agent totals (book of record). | SUM(gross sales) - SUM(redemptions) | Plan = 4% annual organic growth on beginning AUM | green at 100% of target, amber at 50% | Head of Distribution |
| driver | **Gross sales** (`gross_sales`) | New money into our funds (all channels incl. institutional mandates). | SUM(gross sales) | same month last year +5% | green at 100% of target, amber at 90% | Head of Distribution |
| driver | **Redemption rate (annualised)** (`redemption_rate`) | Redemptions as a share of beginning AUM, annualised. The retention side of organic growth. | 12 x SUM(redemptions) / SUM(beginning AUM) | 28% | green <= 28%, amber <= 33% | Head of Distribution |
| driver | **Assets under management** (`ending_aum`) | Month-end AUM across all funds (transfer agent). | SUM(ending AUM) | - | info only | Head of Distribution |
| driver | **Management-fee run rate** (`revenue_run_rate`) | Annual management fees implied by month-end AUM and each fund's fee. | SUM(ending AUM x fee bps / 10,000) | same month last year +5% | green at 100% of target, amber at 95% | Head of Distribution |
| driver | **Share of category gross sales** (`market_share`) | Our gross sales divided by industry gross sales in the categories where we have a fund. | SUM(our gross sales) / SUM(industry gross sales) | first-12-month average +5% | green at 100% of target, amber at 90% | Distribution Strategy & Analytics |
| driver | **Net flows by product family** (`net_flows_by_family`) | Transfer-agent net flows by product family. | SUM(net flows) by family | - | info only | Product Management |
| input | **Meetings per external wholesaler** (`meetings_per_external`) | Completed in-person + virtual meetings per external wholesaler in seat. | SUM(meetings) / COUNT(external wholesalers in seat) | 35 | green at 100% of target, amber at 85% | Regional Sales Directors |
| input | **External wholesaler seats filled** (`external_seats_filled`) | External wholesalers in seat (plan = 16 seats, two per territory). A vacant seat leaves a territory's advisors uncovered. | COUNT(external wholesalers in seat) | 16 | green at 100% of target, amber at 90% | Head of Distribution |
| input | **Meeting-to-sale conversion** (`meeting_conversion`) | Share of meetings where the advisor bought the product family discussed within the meeting month or the next two. The last two months are left out until their window closes. | meetings followed by a purchase of the family / meetings | first-12-month average +5% | green at 100% of target, amber at 90% | Regional Sales Directors |
| input | **Tier-A advisor coverage (90 days)** (`tier_a_coverage`) | Share of tier-A advisors (top 15% by book) who had an external-wholesaler meeting in the last three months. | tier-A advisors met in trailing 3 months / tier-A advisors | 80% | green >= 80%, amber >= 70% | Regional Sales Directors |
| input | **Producing advisors** (`producing_advisors`) | Advisors with at least one purchase in the month (attributed trades). | COUNT(advisors with gross sales > 0) | same month last year +3% | green at 100% of target, amber at 90% | Distribution Strategy & Analytics |
| input | **New & reactivated producers** (`new_producing_advisors`) | Advisors who bought this month after no purchase in the previous 12 months (new or won back). Starts in month 13 so every advisor has a full year of history. | COUNT(advisors buying with zero purchase months in the prior 12) | first-12-month average +5% | green at 100% of target, amber at 85% | Distribution Strategy & Analytics |
| input | **Product families per advisor** (`cross_sell_depth`) | Average number of product families held by advisors who hold any of our funds. | AVG(families held \| AUM > 0) | first-12-month average +3% | green at 100% of target, amber at 97% | Distribution Strategy & Analytics |
| input | **Gross sales per external wholesaler** (`sales_per_external`) | Intermediary gross sales credited to external wholesalers' territories, per wholesaler in seat. Target = sum of quarterly goals / 3. | SUM(credited gross sales) / COUNT(external wholesalers in seat) | computed in SQL | green at 100% of target, amber at 90% | Regional Sales Directors |
| input | **Institutional weighted pipeline** (`inst_weighted_pipeline`) | Open RFP opportunities weighted by stage probability (Identified 10%, RFP 25%, Finalist 50%). | SUM(open mandate size x stage probability) | - | info only | Head of Institutional Sales |
| input | **Institutional win rate (12 months)** (`inst_win_rate_12m`) | Wins as a share of decided opportunities (won + lost at any stage) over the trailing 12 months. | wins / (wins + losses), trailing 12 months | 25% | green >= 25%, amber >= 18% | Head of Institutional Sales |
| input | **External meetings by territory** (`external_meetings_by_territory`) | Completed external-wholesaler meetings by territory. Watched for coverage gaps (vacant seats, leave). | COUNT(completed external meetings) by territory | - | info only | Regional Sales Directors |
| health | **Unattributed sales (rep code not mapped)** (`dq_unattributed_sales`) | Share of intermediary gross sales whose rep code is missing from the crosswalk. Unattributed sales cannot be credited to a wholesaler or used for targeting. | unmapped gross sales / reported gross sales | 2.0% | green <= 2.0%, amber <= 3.0% | Sales Operations / Data Governance |
| health | **Late-reported trades (vendor A)** (`dq_late_trades`) | Share of vendor A trades reported after the month they were placed (they restate last month's numbers). | trades with report month > trade month / trades | 6.0% | green <= 6.0%, amber <= 8.0% | Sales Operations / Data Governance |
| health | **Feed coverage vs transfer agent** (`dq_attribution_coverage`) | Intermediary gross sales seen in the vendor feeds as a share of the transfer agent's intermediary total. The gap is omnibus / retirement-plan flow with no rep detail. | feed gross sales / TA intermediary gross sales | 85% | green >= 85%, amber >= 80% | Sales Operations / Data Governance |
| health | **CRM duplicate sync rate** (`dq_crm_duplicates`) | Share of raw CRM activity rows that were duplicate syncs of an activity already received. | (raw rows - distinct activities) / raw rows | 3.0% | green <= 3.0%, amber <= 5.0% | Sales Operations / Data Governance |

## SQL

Each KPI runs this SQL unchanged on SQLite and Spark.

### Organic growth rate (annualised)

```sql
SELECT month_key, SUM(net_flows) * 12 / NULLIF(SUM(beginning_aum), 0) AS value
FROM mart_product_month GROUP BY month_key
```

### Net flows

```sql
SELECT month_key, SUM(net_flows) AS value, SUM(beginning_aum) * 0.04 / 12 AS target
FROM mart_product_month GROUP BY month_key
```

### Gross sales

```sql
SELECT month_key, SUM(gross_sales) AS value FROM mart_product_month GROUP BY month_key
```

### Redemption rate (annualised)

```sql
SELECT month_key, SUM(redemptions) * 12 / NULLIF(SUM(beginning_aum), 0) AS value
FROM mart_product_month GROUP BY month_key
```

### Assets under management

```sql
SELECT month_key, SUM(ending_aum) AS value FROM mart_product_month GROUP BY month_key
```

### Management-fee run rate

```sql
SELECT month_key, SUM(revenue_run_rate) AS value FROM mart_product_month GROUP BY month_key
```

### Share of category gross sales

```sql
SELECT month_key, SUM(our_gross_sales) / NULLIF(SUM(industry_gross_sales), 0) AS value
FROM mart_market_share GROUP BY month_key
```

### Gross sales per external wholesaler

```sql
SELECT month_key,
       SUM(credited_gross_sales) / COUNT(DISTINCT wholesaler_id) AS value,
       SUM(monthly_goal) / COUNT(DISTINCT wholesaler_id) AS target
FROM mart_wholesaler_month WHERE role = 'External' GROUP BY month_key
```

### Meetings per external wholesaler

```sql
SELECT month_key,
       CAST(SUM(in_person_meetings + virtual_meetings) AS DOUBLE) / COUNT(DISTINCT wholesaler_id) AS value
FROM mart_wholesaler_month WHERE role = 'External' GROUP BY month_key
```

### External wholesaler seats filled

```sql
SELECT month_key, CAST(COUNT(DISTINCT wholesaler_id) AS DOUBLE) AS value
FROM mart_wholesaler_month WHERE role = 'External' GROUP BY month_key
```

### Meeting-to-sale conversion

```sql
SELECT month_key, AVG(CAST(converted_3m AS DOUBLE)) AS value
FROM mart_activity_conversion
WHERE activity_type IN ('In-Person Meeting', 'Virtual Meeting')
  AND month_index <= (SELECT MAX(month_index) - 2 FROM dim_month)
GROUP BY month_key
```

### Tier-A advisor coverage (90 days)

```sql
SELECT month_key,
       AVG(CASE WHEN external_meetings_3m > 0 THEN CAST(1 AS DOUBLE) ELSE CAST(0 AS DOUBLE) END) AS value
FROM mart_advisor_month WHERE tier = 'A' AND month_index >= 3 GROUP BY month_key
```

### Producing advisors

```sql
SELECT month_key, CAST(COUNT(*) AS DOUBLE) AS value
FROM mart_advisor_month WHERE gross_sales > 0 GROUP BY month_key
```

### New & reactivated producers

```sql
SELECT month_key, CAST(COUNT(*) AS DOUBLE) AS value
FROM mart_advisor_month
WHERE gross_sales > 0 AND COALESCE(purchase_months_prior_12m, 0) = 0 AND month_index >= 13
GROUP BY month_key
```

### Product families per advisor

```sql
SELECT month_key, AVG(CAST(families_held AS DOUBLE)) AS value
FROM mart_advisor_month WHERE aum > 0 GROUP BY month_key
```

### Institutional weighted pipeline

```sql
SELECT month_key,
       SUM(CASE WHEN is_open = 1 THEN mandate_size_usd * stage_probability ELSE 0 END) AS value
FROM mart_inst_pipeline GROUP BY month_key
```

### Institutional win rate (12 months)

```sql
SELECT month_key, value FROM (
    SELECT month_key, month_index,
           CAST(SUM(wins) OVER w AS DOUBLE) / NULLIF(SUM(decided) OVER w, 0) AS value
    FROM (
        SELECT m.month_key, m.month_index,
               COALESCE(SUM(p.won_this_month), 0) AS wins,
               COALESCE(SUM(p.decided_this_month), 0) AS decided
        FROM dim_month m
        LEFT JOIN mart_inst_pipeline p ON m.month_key = p.month_key
        GROUP BY m.month_key, m.month_index
    ) d
    WINDOW w AS (ORDER BY month_index ROWS BETWEEN 11 PRECEDING AND CURRENT ROW)
) x
WHERE month_index >= 12
```

### Unattributed sales (rep code not mapped)

```sql
SELECT month_key,
       SUM(CASE WHEN is_mapped = 0 THEN gross_sales ELSE 0 END) / NULLIF(SUM(gross_sales), 0) AS value
FROM fct_trades GROUP BY month_key
```

### Feed coverage vs transfer agent

```sql
SELECT month_key, SUM(feed_gross) / NULLIF(SUM(intermediary_gross), 0) AS value
FROM mart_product_month GROUP BY month_key
```

### Late-reported trades (vendor A)

```sql
SELECT month_key, AVG(CAST(is_late AS DOUBLE)) AS value
FROM fct_trades WHERE source_vendor = 'A' GROUP BY month_key
```

### CRM duplicate sync rate

```sql
SELECT s.month_key,
       CAST(COUNT(*) - COUNT(DISTINCT r.activity_id) AS DOUBLE) / COUNT(*) AS value
FROM raw_crm_activities r
JOIN stg_activities s ON r.activity_id = s.activity_id
GROUP BY s.month_key
```

### External meetings by territory

```sql
SELECT a.month_key, w.territory_code AS dim, CAST(COUNT(*) AS DOUBLE) AS value
FROM stg_activities a
JOIN stg_wholesalers w ON a.wholesaler_id = w.wholesaler_id
WHERE a.is_completed = 1 AND a.is_meeting = 1 AND w.role = 'External'
GROUP BY a.month_key, w.territory_code
```

### Net flows by product family

```sql
SELECT month_key, family_name AS dim, SUM(net_flows) AS value
FROM mart_product_month GROUP BY month_key, family_name
```
