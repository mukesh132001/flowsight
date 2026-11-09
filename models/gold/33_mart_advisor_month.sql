-- indexes: (advisor_key, month_index) (month_key)
-- Advisor x month panel: assets with us, flows, coverage and engagement. Feeds the
-- coverage / breadth KPIs and the redemption early-warning model.
WITH grid AS (
    SELECT a.advisor_key, a.tier, a.channel, a.channel_group, a.territory_code, a.book_aum_est,
           m.month_key, m.month_index
    FROM stg_advisors a
    CROSS JOIN dim_month m
),
trades AS (
    SELECT advisor_key, month_key,
           SUM(gross_sales) AS gross_sales,
           SUM(redemptions) AS redemptions
    FROM fct_trades
    WHERE is_mapped = 1
    GROUP BY advisor_key, month_key
),
pos AS (
    SELECT advisor_key, month_key,
           SUM(market_value)           AS aum,
           COUNT(DISTINCT family_code) AS families_held
    FROM fct_positions
    WHERE advisor_key IS NOT NULL
    GROUP BY advisor_key, month_key
),
acts AS (
    SELECT advisor_key, month_key,
           SUM(CASE WHEN is_completed = 1 AND is_meeting = 1 THEN 1 ELSE 0 END)            AS meetings,
           SUM(CASE WHEN is_completed = 1 AND activity_type = 'Call' THEN 1 ELSE 0 END)    AS calls,
           SUM(CASE WHEN is_completed = 1 AND activity_type = 'Email' THEN 1 ELSE 0 END)   AS emails,
           SUM(CASE WHEN is_completed = 1 AND is_meeting = 1
                     AND wholesaler_role = 'External' THEN 1 ELSE 0 END)                    AS external_meetings,
           SUM(CASE WHEN is_completed = 0 THEN 1 ELSE 0 END)                                AS cancelled_activities
    FROM stg_activities
    WHERE advisor_key IS NOT NULL
    GROUP BY advisor_key, month_key
),
web AS (
    SELECT advisor_key, month_key, COUNT(*) AS web_events
    FROM fct_web_events
    WHERE advisor_key IS NOT NULL
    GROUP BY advisor_key, month_key
),
joined AS (
    SELECT
        g.*,
        COALESCE(p.aum, 0)                 AS aum,
        COALESCE(p.families_held, 0)       AS families_held,
        COALESCE(t.gross_sales, 0)         AS gross_sales,
        COALESCE(t.redemptions, 0)         AS redemptions,
        COALESCE(c.meetings, 0)            AS meetings,
        COALESCE(c.calls, 0)               AS calls,
        COALESCE(c.emails, 0)              AS emails,
        COALESCE(c.external_meetings, 0)   AS external_meetings,
        COALESCE(c.cancelled_activities, 0) AS cancelled_activities,
        COALESCE(w.web_events, 0)          AS web_events
    FROM grid g
    LEFT JOIN pos p    ON g.advisor_key = p.advisor_key AND g.month_key = p.month_key
    LEFT JOIN trades t ON g.advisor_key = t.advisor_key AND g.month_key = t.month_key
    LEFT JOIN acts c   ON g.advisor_key = c.advisor_key AND g.month_key = c.month_key
    LEFT JOIN web w    ON g.advisor_key = w.advisor_key AND g.month_key = w.month_key
)
SELECT
    j.*,
    j.gross_sales - j.redemptions AS net_flows,
    LAG(j.aum) OVER (PARTITION BY j.advisor_key ORDER BY j.month_index) AS prior_aum,
    MAX(CASE WHEN j.meetings + j.calls > 0 THEN j.month_index END)
        OVER (PARTITION BY j.advisor_key ORDER BY j.month_index
              ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)       AS last_contact_index,
    MIN(CASE WHEN j.gross_sales > 0 THEN j.month_index END)
        OVER (PARTITION BY j.advisor_key)                             AS first_purchase_index,
    SUM(j.external_meetings)
        OVER (PARTITION BY j.advisor_key ORDER BY j.month_index
              ROWS BETWEEN 2 PRECEDING AND CURRENT ROW)               AS external_meetings_3m,
    SUM(CASE WHEN j.gross_sales > 0 THEN 1 ELSE 0 END)
        OVER (PARTITION BY j.advisor_key ORDER BY j.month_index
              ROWS BETWEEN 12 PRECEDING AND 1 PRECEDING)              AS purchase_months_prior_12m
FROM joined j
