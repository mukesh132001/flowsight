-- indexes: (month_key) (advisor_key, family_code)
-- Feature store for next-best-action: one row per advisor x product family x month.
-- Features use only data up to and including month t; columns starting y_ / t_ look
-- forward (labels / treatment) and are only used for training and evaluation.
WITH fams AS (
    SELECT DISTINCT family_code FROM stg_products
),
grid AS (
    SELECT a.advisor_key, f.family_code, m.month_key, m.month_index
    FROM stg_advisors a
    CROSS JOIN fams f
    CROSS JOIN dim_month m
    WHERE m.month_index >= 1
),
buy AS (
    SELECT advisor_key, family_code, month_key,
           SUM(gross_sales) AS gross_sales, SUM(redemptions) AS redemptions
    FROM fct_trades
    WHERE is_mapped = 1
    GROUP BY advisor_key, family_code, month_key
),
pos AS (
    SELECT advisor_key, family_code, month_key, SUM(market_value) AS aum
    FROM fct_positions
    WHERE advisor_key IS NOT NULL
    GROUP BY advisor_key, family_code, month_key
),
act AS (
    SELECT advisor_key, family_code, month_key,
           SUM(CASE WHEN is_completed = 1 THEN touch_weight ELSE 0 END)                 AS touch_score,
           SUM(CASE WHEN is_completed = 1 AND is_meeting = 1 THEN 1 ELSE 0 END)         AS fam_meetings,
           SUM(CASE WHEN is_completed = 1 AND activity_type = 'Call' THEN 1 ELSE 0 END) AS fam_calls
    FROM fct_activity_families
    WHERE advisor_key IS NOT NULL
    GROUP BY advisor_key, family_code, month_key
),
web AS (
    SELECT advisor_key, family_code, month_key,
           SUM(CASE WHEN event_type = 'factsheet_download' THEN 1 ELSE 0 END) AS factsheets,
           SUM(CASE WHEN event_type = 'webinar_attended'   THEN 1 ELSE 0 END) AS webinars,
           SUM(CASE WHEN event_type = 'email_click'        THEN 1 ELSE 0 END) AS email_clicks
    FROM fct_web_events
    WHERE advisor_key IS NOT NULL AND family_code IS NOT NULL
    GROUP BY advisor_key, family_code, month_key
),
perf AS (
    SELECT family_code, month_key, AVG(excess_return) AS fam_excess_return
    FROM mart_product_month
    WHERE excess_return IS NOT NULL
    GROUP BY family_code, month_key
),
shelf AS (
    SELECT s.firm_id, p.family_code, m.month_key, COUNT(*) AS shelf_products
    FROM stg_shelf s
    JOIN stg_products p ON s.product_code = p.product_code
    JOIN dim_month m    ON s.approved_month_key IS NOT NULL
                       AND m.month_key >= s.approved_month_key
                       AND (p.launch_month_key IS NULL OR m.month_key >= p.launch_month_key)
    GROUP BY s.firm_id, p.family_code, m.month_key
),
base AS (
    SELECT
        g.advisor_key, g.family_code, g.month_key, g.month_index,
        COALESCE(b.gross_sales, 0)       AS gross_m,
        COALESCE(b.redemptions, 0)       AS red_m,
        COALESCE(p.aum, 0)               AS aum_m,
        COALESCE(a.touch_score, 0)       AS touch_m,
        COALESCE(a.fam_meetings, 0)      AS meet_m,
        COALESCE(a.fam_calls, 0)         AS call_m,
        COALESCE(w.factsheets, 0)        AS fs_m,
        COALESCE(w.webinars, 0)          AS webinar_m,
        COALESCE(w.email_clicks, 0)      AS click_m,
        COALESCE(pf.fam_excess_return, 0) AS perf_m,
        COALESCE(sh.shelf_products, 0)   AS shelf_products
    FROM grid g
    LEFT JOIN buy b   ON g.advisor_key = b.advisor_key AND g.family_code = b.family_code AND g.month_key = b.month_key
    LEFT JOIN pos p   ON g.advisor_key = p.advisor_key AND g.family_code = p.family_code AND g.month_key = p.month_key
    LEFT JOIN act a   ON g.advisor_key = a.advisor_key AND g.family_code = a.family_code AND g.month_key = a.month_key
    LEFT JOIN web w   ON g.advisor_key = w.advisor_key AND g.family_code = w.family_code AND g.month_key = w.month_key
    LEFT JOIN perf pf ON g.family_code = pf.family_code AND g.month_key = pf.month_key
    LEFT JOIN int_advisor_firm_month af ON g.advisor_key = af.advisor_key AND g.month_key = af.month_key
    LEFT JOIN shelf sh ON af.firm_id = sh.firm_id AND g.family_code = sh.family_code AND g.month_key = sh.month_key
)
SELECT
    advisor_key,
    family_code,
    month_key,
    month_index,
    aum_m                                   AS fam_aum,
    CASE WHEN aum_m > 0 THEN 1 ELSE 0 END   AS holds_family,
    shelf_products,
    gross_m                                 AS gross_1m,
    SUM(gross_m)  OVER w3                   AS gross_3m,
    SUM(gross_m)  OVER w12                  AS gross_12m,
    SUM(red_m)    OVER w3                   AS red_3m,
    touch_m                                 AS touch_1m,
    SUM(touch_m)  OVER w3                   AS touch_3m,
    SUM(meet_m)   OVER w12                  AS meetings_12m,
    SUM(call_m)   OVER w3                   AS calls_3m,
    fs_m + webinar_m + click_m              AS digital_1m,
    SUM(fs_m + webinar_m + click_m) OVER w3 AS digital_3m,
    fs_m                                    AS factsheets_1m,
    webinar_m                               AS webinars_1m,
    SUM(perf_m)   OVER w3                   AS fam_excess_3m,
    month_index - MAX(CASE WHEN gross_m > 0 THEN month_index END) OVER wall AS months_since_buy,
    month_index - MAX(CASE WHEN touch_m > 0 THEN month_index END) OVER wall AS months_since_touch,
    -- forward-looking columns (never used as features)
    COALESCE(SUM(gross_m) OVER wnext2, 0)   AS y_gross_next2,
    CASE WHEN COALESCE(SUM(gross_m) OVER wnext2, 0) > 0 THEN 1 ELSE 0 END AS y_buy_next2,
    COALESCE(LEAD(touch_m, 1) OVER wo, 0)   AS t_touch_next1,
    COALESCE(LEAD(meet_m, 1) OVER wo, 0)    AS t_meet_next1
FROM base
WINDOW
    wo     AS (PARTITION BY advisor_key, family_code ORDER BY month_index),
    w3     AS (PARTITION BY advisor_key, family_code ORDER BY month_index ROWS BETWEEN 2 PRECEDING AND CURRENT ROW),
    w12    AS (PARTITION BY advisor_key, family_code ORDER BY month_index ROWS BETWEEN 11 PRECEDING AND CURRENT ROW),
    wall   AS (PARTITION BY advisor_key, family_code ORDER BY month_index ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW),
    wnext2 AS (PARTITION BY advisor_key, family_code ORDER BY month_index ROWS BETWEEN 1 FOLLOWING AND 2 FOLLOWING)
