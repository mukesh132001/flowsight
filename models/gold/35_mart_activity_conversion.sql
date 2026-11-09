-- indexes: (month_key) (wholesaler_id)
-- Did a meeting or call about a product family turn into a purchase of that family by the
-- same advisor in the activity month or the two months after? (3-month window)
WITH buys AS (
    SELECT t.advisor_key, t.family_code, m.month_index, SUM(t.gross_sales) AS gross_sales
    FROM fct_trades t
    JOIN dim_month m ON t.month_key = m.month_key
    WHERE t.is_mapped = 1 AND t.gross_sales > 0
    GROUP BY t.advisor_key, t.family_code, m.month_index
),
acts AS (
    SELECT f.activity_id, f.advisor_key, f.wholesaler_id, f.wholesaler_role, f.activity_type,
           f.family_code, f.month_key, m.month_index
    FROM fct_activity_families f
    JOIN dim_month m ON f.month_key = m.month_key
    WHERE f.is_completed = 1 AND f.activity_type <> 'Email' AND f.advisor_key IS NOT NULL
)
SELECT
    a.activity_id,
    a.advisor_key,
    a.wholesaler_id,
    a.wholesaler_role,
    a.activity_type,
    a.family_code,
    a.month_key,
    a.month_index,
    CASE WHEN SUM(b.gross_sales) > 0 THEN 1 ELSE 0 END AS converted_3m,
    COALESCE(SUM(b.gross_sales), 0)                    AS gross_sales_3m
FROM acts a
LEFT JOIN buys b
       ON a.advisor_key = b.advisor_key
      AND a.family_code = b.family_code
      AND b.month_index BETWEEN a.month_index AND a.month_index + 2
GROUP BY a.activity_id, a.advisor_key, a.wholesaler_id, a.wholesaler_role, a.activity_type,
         a.family_code, a.month_key, a.month_index
