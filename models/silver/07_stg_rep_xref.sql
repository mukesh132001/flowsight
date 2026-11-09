-- indexes: (rep_code)
-- Rep-code crosswalk with effective dates (advisors change rep codes when they move firms).
SELECT
    TRIM(rep_code) AS rep_code,
    advisor_key,
    firm_id,
    CAST(SUBSTR(effective_start, 1, 4) || SUBSTR(effective_start, 6, 2) AS INTEGER) AS start_month_key,
    CASE WHEN effective_end IS NULL THEN 999912
         ELSE CAST(SUBSTR(effective_end, 1, 4) || SUBSTR(effective_end, 6, 2) AS INTEGER)
    END AS end_month_key
FROM raw_rep_code_xref
