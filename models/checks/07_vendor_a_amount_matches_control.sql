-- severity: error
-- description: The vendor A file sums to the control total the sender declared (to the dollar); a missing control row also fails.
SELECT 'sales_vendor_a.csv' AS feed
FROM (SELECT SUM(CAST(amount AS DOUBLE)) AS total FROM raw_sales_vendor_a) a
LEFT JOIN raw_control_totals c ON c.feed = 'sales_vendor_a.csv'
WHERE c.feed IS NULL
   OR ABS(CAST(c.amount_total AS DOUBLE) - a.total) > 1
