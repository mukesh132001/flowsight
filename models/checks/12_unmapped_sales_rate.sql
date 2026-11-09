-- severity: warn
-- description: Months where more than 3% of reported gross sales could not be attributed to an advisor (rep code missing from the crosswalk).
SELECT month_key,
       SUM(CASE WHEN is_mapped = 0 THEN gross_sales ELSE 0 END) / SUM(gross_sales) AS unmapped_share
FROM fct_trades
GROUP BY month_key
HAVING SUM(CASE WHEN is_mapped = 0 THEN gross_sales ELSE 0 END) / SUM(gross_sales) > 0.03
