-- Share of industry gross sales by fund category (our TA gross sales / industry).
WITH ours AS (
    SELECT p.category, t.month_key, SUM(t.gross_sales) AS our_gross_sales
    FROM stg_ta_flows t
    JOIN stg_products p ON t.product_code = p.product_code
    GROUP BY p.category, t.month_key
)
SELECT
    i.category,
    i.month_key,
    o.our_gross_sales,
    i.industry_gross_sales,
    o.our_gross_sales / NULLIF(i.industry_gross_sales, 0) AS market_share
FROM stg_industry_flows i
JOIN ours o ON i.category = o.category AND i.month_key = o.month_key
