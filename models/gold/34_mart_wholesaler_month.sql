-- indexes: (wholesaler_id, month_key) (month_key)
-- Wholesaler scorecard. Externals are credited with sales in their territory + channel
-- group, internals with their whole territory. Months a seat is vacant credit nobody.
WITH wm AS (
    SELECT w.wholesaler_id, w.wholesaler_name, w.role, w.territory_code, w.channel_group,
           m.month_key, m.month_index, m.quarter_label
    FROM stg_wholesalers w
    JOIN dim_month m ON m.month_key BETWEEN w.start_month_key AND w.end_month_key
    WHERE w.role IN ('External', 'Internal') AND m.month_index >= 1
),
acts AS (
    SELECT wholesaler_id, month_key,
           SUM(CASE WHEN is_completed = 1 AND activity_type = 'In-Person Meeting' THEN 1 ELSE 0 END) AS in_person_meetings,
           SUM(CASE WHEN is_completed = 1 AND activity_type = 'Virtual Meeting'   THEN 1 ELSE 0 END) AS virtual_meetings,
           SUM(CASE WHEN is_completed = 1 AND activity_type = 'Call'              THEN 1 ELSE 0 END) AS calls,
           SUM(CASE WHEN is_completed = 1 AND activity_type = 'Email'             THEN 1 ELSE 0 END) AS emails,
           SUM(CASE WHEN is_completed = 0 THEN 1 ELSE 0 END)                                         AS cancelled,
           COUNT(DISTINCT CASE WHEN is_completed = 1 AND activity_type <> 'Email' THEN advisor_key END) AS advisors_touched
    FROM stg_activities
    WHERE wholesaler_id IS NOT NULL
    GROUP BY wholesaler_id, month_key
),
sales_tg AS (
    SELECT a.territory_code, t.channel_group, t.month_key,
           SUM(t.gross_sales) AS gross_sales, SUM(t.redemptions) AS redemptions
    FROM fct_trades t
    JOIN stg_advisors a ON t.advisor_key = a.advisor_key
    GROUP BY a.territory_code, t.channel_group, t.month_key
),
sales_t AS (
    SELECT territory_code, month_key, SUM(gross_sales) AS gross_sales, SUM(redemptions) AS redemptions
    FROM sales_tg
    GROUP BY territory_code, month_key
)
SELECT
    wm.wholesaler_id,
    wm.wholesaler_name,
    wm.role,
    wm.territory_code,
    wm.channel_group,
    wm.month_key,
    wm.month_index,
    wm.quarter_label,
    COALESCE(a.in_person_meetings, 0) AS in_person_meetings,
    COALESCE(a.virtual_meetings, 0)   AS virtual_meetings,
    COALESCE(a.calls, 0)              AS calls,
    COALESCE(a.emails, 0)             AS emails,
    COALESCE(a.cancelled, 0)          AS cancelled,
    COALESCE(a.advisors_touched, 0)   AS advisors_touched,
    COALESCE(CASE WHEN wm.role = 'External' THEN s.gross_sales ELSE st.gross_sales END, 0) AS credited_gross_sales,
    COALESCE(CASE WHEN wm.role = 'External' THEN s.redemptions ELSE st.redemptions END, 0) AS credited_redemptions,
    g.goal_gross_sales_usd / 3 AS monthly_goal
FROM wm
LEFT JOIN acts a       ON wm.wholesaler_id = a.wholesaler_id AND wm.month_key = a.month_key
LEFT JOIN sales_tg s   ON wm.territory_code = s.territory_code AND wm.channel_group = s.channel_group
                      AND wm.month_key = s.month_key
LEFT JOIN sales_t st   ON wm.territory_code = st.territory_code AND wm.month_key = st.month_key
LEFT JOIN stg_sales_goals g ON wm.wholesaler_id = g.wholesaler_id AND wm.quarter_label = g.quarter_label
