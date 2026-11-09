-- severity: warn
-- description: Months where more than 8% of vendor A trades were reported after month-end (late-arriving data).
SELECT month_key, AVG(CAST(is_late AS DOUBLE)) AS late_share
FROM fct_trades
WHERE source_vendor = 'A'
GROUP BY month_key
HAVING AVG(CAST(is_late AS DOUBLE)) > 0.08
