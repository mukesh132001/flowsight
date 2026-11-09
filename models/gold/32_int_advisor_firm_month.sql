-- indexes: (advisor_key, month_key) (firm_id, month_key)
-- Which firm each advisor was at in each month (from the rep-code crosswalk).
SELECT
    x.advisor_key,
    m.month_key,
    m.month_index,
    MIN(x.firm_id) AS firm_id
FROM stg_rep_xref x
JOIN dim_month m ON m.month_key BETWEEN x.start_month_key AND x.end_month_key
GROUP BY x.advisor_key, m.month_key, m.month_index
