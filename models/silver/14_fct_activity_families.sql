-- indexes: (advisor_key, family_code, month_key) (activity_id)
-- Which product families each activity covered. The CRM junction holds fund codes or,
-- for some rows, fund names - match on either.
SELECT DISTINCT
    a.activity_id,
    a.advisor_key,
    a.wholesaler_id,
    a.wholesaler_role,
    a.month_key,
    a.activity_type,
    a.is_completed,
    a.is_meeting,
    a.touch_weight,
    p.family_code
FROM raw_crm_activity_products ap
JOIN stg_activities a ON ap.activity_id = a.activity_id
JOIN stg_products p   ON TRIM(ap.product) = p.product_code OR TRIM(ap.product) = p.fund_name
