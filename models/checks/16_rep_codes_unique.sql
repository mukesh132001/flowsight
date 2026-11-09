-- severity: error
-- description: A rep code maps to at most one advisor in any month (overlapping crosswalk rows would double-count trades).
SELECT a.rep_code
FROM stg_rep_xref a
JOIN stg_rep_xref b
  ON a.rep_code = b.rep_code
 AND a.advisor_key < b.advisor_key
 AND a.start_month_key <= b.end_month_key
 AND b.start_month_key <= a.end_month_key
