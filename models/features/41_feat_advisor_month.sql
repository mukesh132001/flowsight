-- indexes: (month_key) (advisor_key)
-- Feature store for the redemption early-warning model: one row per advisor x month.
-- y_red_next3 looks forward (label only).
WITH recent_move AS (
    -- months 0-5 after an advisor started under a new rep code (i.e. changed firms)
    SELECT DISTINCT x.advisor_key, m.month_key
    FROM stg_rep_xref x
    JOIN dim_month s ON s.month_key = x.start_month_key
    JOIN dim_month m ON m.month_index BETWEEN s.month_index AND s.month_index + 5
),
prod_perf AS (
    -- each fund's excess return vs its category over the trailing 3 months
    SELECT product_code, month_key,
           SUM(excess_return) OVER (PARTITION BY product_code ORDER BY month_index
                                    ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) AS excess_3m
    FROM mart_product_month
),
fam_trend AS (
    -- industry-wide momentum of each family: our 3-month net flows / AUM
    SELECT family_code, month_key,
           SUM(nf) OVER (PARTITION BY family_code ORDER BY month_index ROWS BETWEEN 2 PRECEDING AND CURRENT ROW)
             / NULLIF(SUM(aum) OVER (PARTITION BY family_code ORDER BY month_index ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 0)
             AS family_flow_rate_3m
    FROM (SELECT family_code, month_key, month_index, SUM(net_flows) AS nf, SUM(ending_aum) AS aum
          FROM mart_product_month GROUP BY family_code, month_key, month_index) f
),
held_perf AS (
    -- asset-weighted performance and flow momentum of what the advisor holds
    SELECT p.advisor_key, p.month_key,
           SUM(p.market_value * COALESCE(pp.excess_3m, 0)) / NULLIF(SUM(p.market_value), 0)          AS held_excess_3m,
           SUM(p.market_value * COALESCE(ft.family_flow_rate_3m, 0)) / NULLIF(SUM(p.market_value), 0) AS held_family_flow_rate,
           COUNT(*)                                                                                   AS n_holdings,
           SUM(CASE WHEN p.market_value < 50000 THEN 1 ELSE 0 END)                                     AS small_holdings
    FROM fct_positions p
    JOIN prod_perf pp     ON p.product_code = pp.product_code AND p.month_key = pp.month_key
    LEFT JOIN fam_trend ft ON p.family_code = ft.family_code AND p.month_key = ft.month_key
    WHERE p.advisor_key IS NOT NULL
    GROUP BY p.advisor_key, p.month_key
),
base AS (
    SELECT am.*,
           CASE WHEN rm.advisor_key IS NULL THEN 0 ELSE 1 END AS moved_recently,
           COALESCE(hp.held_excess_3m, 0)        AS held_excess_3m,
           COALESCE(hp.held_family_flow_rate, 0) AS held_family_flow_rate,
           COALESCE(hp.n_holdings, 0)            AS n_holdings,
           COALESCE(hp.small_holdings, 0)        AS small_holdings
    FROM mart_advisor_month am
    LEFT JOIN recent_move rm ON am.advisor_key = rm.advisor_key AND am.month_key = rm.month_key
    LEFT JOIN held_perf hp   ON am.advisor_key = hp.advisor_key AND am.month_key = hp.month_key
)
SELECT
    advisor_key,
    month_key,
    month_index,
    tier,
    channel,
    channel_group,
    territory_code,
    book_aum_est,
    aum,
    families_held,
    LAG(aum, 3) OVER wo                               AS aum_3m_ago,
    SUM(gross_sales) OVER w3                          AS gross_3m,
    SUM(redemptions) OVER w3                          AS red_3m,
    SUM(redemptions) OVER w12                         AS red_12m,
    SUM(meetings + calls) OVER w3                     AS contacts_3m,
    SUM(meetings + calls) OVER w6                     AS contacts_6m,
    SUM(cancelled_activities) OVER w3                 AS cancelled_3m,
    SUM(web_events) OVER w3                           AS web_3m,
    SUM(web_events) OVER wprev3                       AS web_prev3m,
    month_index - last_contact_index                  AS months_since_contact,
    moved_recently,
    held_excess_3m,
    held_family_flow_rate,
    n_holdings,
    small_holdings,
    COALESCE(SUM(redemptions) OVER wnext3, 0)         AS y_red_next3
FROM base
WINDOW
    wo     AS (PARTITION BY advisor_key ORDER BY month_index),
    w3     AS (PARTITION BY advisor_key ORDER BY month_index ROWS BETWEEN 2 PRECEDING AND CURRENT ROW),
    w6     AS (PARTITION BY advisor_key ORDER BY month_index ROWS BETWEEN 5 PRECEDING AND CURRENT ROW),
    w12    AS (PARTITION BY advisor_key ORDER BY month_index ROWS BETWEEN 11 PRECEDING AND CURRENT ROW),
    wprev3 AS (PARTITION BY advisor_key ORDER BY month_index ROWS BETWEEN 5 PRECEDING AND 3 PRECEDING),
    wnext3 AS (PARTITION BY advisor_key ORDER BY month_index ROWS BETWEEN 1 FOLLOWING AND 3 FOLLOWING)
