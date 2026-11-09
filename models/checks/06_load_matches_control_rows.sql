-- severity: error
-- description: Rows loaded from each feed equal the row count the sender declared in its control file.
SELECT c.feed
FROM raw_control_totals c
JOIN load_audit l ON c.feed = l.feed
WHERE CAST(c.row_count AS INTEGER) <> l.rows_loaded
