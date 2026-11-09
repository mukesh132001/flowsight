-- severity: error
-- description: Rows loaded from each feed equal the row count the sender declared in its control file (a missing feed or an empty control file also fails).
SELECT c.feed
FROM raw_control_totals c
LEFT JOIN load_audit l ON c.feed = l.feed
WHERE l.rows_loaded IS NULL OR CAST(c.row_count AS INTEGER) <> l.rows_loaded
UNION ALL
SELECT feed
FROM load_audit
WHERE table_name = 'raw_control_totals' AND rows_loaded = 0
