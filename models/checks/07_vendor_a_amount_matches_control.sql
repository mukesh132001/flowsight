-- severity: error
-- description: The vendor A file sums to the control total the sender declared (to the dollar).
SELECT c.feed
FROM raw_control_totals c
CROSS JOIN (SELECT SUM(CAST(amount AS DOUBLE)) AS total FROM raw_sales_vendor_a) a
WHERE c.feed = 'sales_vendor_a.csv'
  AND ABS(CAST(c.amount_total AS DOUBLE) - a.total) > 1
