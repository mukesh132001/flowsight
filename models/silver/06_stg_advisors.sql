-- indexes: (advisor_key) (crm_contact_id) (email_hash)
-- Golden advisor record: the vendor file re-sends stale rows, keep the latest per advisor.
WITH ranked AS (
    SELECT a.*,
           ROW_NUMBER() OVER (PARTITION BY advisor_key ORDER BY last_updated DESC) AS rn
    FROM raw_advisor_master a
)
SELECT
    r.advisor_key,
    r.first_name || ' ' || r.last_name   AS advisor_name,
    r.firm_id,
    f.firm_name,
    f.channel,
    f.channel_group,
    r.branch_state,
    t.territory_code,
    t.territory_name,
    t.region,
    r.tier,
    r.practice_focus,
    CAST(r.book_aum_est AS DOUBLE)        AS book_aum_est,
    r.crm_contact_id,
    r.email_hash,
    CAST(r.industry_tenure_years AS INTEGER) AS industry_tenure_years
FROM ranked r
LEFT JOIN stg_firms f       ON r.firm_id = f.firm_id
LEFT JOIN stg_territories t ON r.branch_state = t.state
WHERE r.rn = 1
