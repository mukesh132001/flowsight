-- indexes: (advisor_key, month_key)
-- Digital engagement from marketing automation, matched to advisors by hashed e-mail.
SELECT
    e.event_id,
    SUBSTR(e.event_ts, 1, 10) AS event_date,
    CAST(SUBSTR(e.event_ts, 1, 4) || SUBSTR(e.event_ts, 6, 2) AS INTEGER) AS month_key,
    a.advisor_key,
    CASE WHEN a.advisor_key IS NULL THEN 0 ELSE 1 END AS is_known_contact,
    e.event_type,
    e.product_code,
    p.family_code
FROM raw_web_engagement e
LEFT JOIN stg_advisors a ON e.email_hash = a.email_hash
LEFT JOIN stg_products p ON e.product_code = p.product_code
