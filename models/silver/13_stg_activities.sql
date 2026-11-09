-- indexes: (advisor_key, month_key) (wholesaler_id, month_key) (activity_id)
-- CRM activities: keep the latest sync of each activity, map 14 spellings to 4 types,
-- parse both date formats, attach the wholesaler (owner e-mail) and the advisor (contact).
WITH ranked AS (
    SELECT c.*,
           ROW_NUMBER() OVER (PARTITION BY activity_id ORDER BY last_modified DESC) AS rn
    FROM raw_crm_activities c
),
std AS (
    SELECT
        activity_id,
        LOWER(TRIM(owner_email)) AS owner_email,
        contact_id,
        status,
        activity_type            AS activity_type_raw,
        CASE
            WHEN UPPER(TRIM(activity_type)) IN ('IN-PERSON MEETING', 'MEETING', 'MTG - IN PERSON') THEN 'In-Person Meeting'
            WHEN UPPER(TRIM(activity_type)) IN ('VIRTUAL MEETING', 'ZOOM MEETING', 'TEAMS MTG')    THEN 'Virtual Meeting'
            WHEN UPPER(TRIM(activity_type)) IN ('CALL', 'PHONE CALL')                              THEN 'Call'
            WHEN UPPER(TRIM(activity_type)) IN ('EMAIL', 'E-MAIL')                                 THEN 'Email'
            ELSE 'Other'
        END AS activity_type,
        CASE WHEN INSTR(activity_datetime, '/') > 0
             THEN SUBSTR(activity_datetime, 7, 4) || '-' || SUBSTR(activity_datetime, 1, 2) || '-' || SUBSTR(activity_datetime, 4, 2)
             ELSE SUBSTR(activity_datetime, 1, 10)
        END AS activity_date
    FROM ranked
    WHERE rn = 1
)
SELECT
    s.activity_id,
    s.activity_date,
    CAST(SUBSTR(s.activity_date, 1, 4) || SUBSTR(s.activity_date, 6, 2) AS INTEGER) AS month_key,
    w.wholesaler_id,
    w.role                 AS wholesaler_role,
    a.advisor_key,
    s.activity_type,
    s.activity_type_raw,
    CASE WHEN s.status = 'Completed' THEN 1 ELSE 0 END AS is_completed,
    CASE WHEN s.activity_type IN ('In-Person Meeting', 'Virtual Meeting') THEN 1 ELSE 0 END AS is_meeting,
    -- touch weights (documented in docs/kpi-framework.md): meeting 1.0, virtual 0.75, call 0.45, email 0.08
    CAST(CASE s.activity_type
             WHEN 'In-Person Meeting' THEN 100
             WHEN 'Virtual Meeting'   THEN 75
             WHEN 'Call'              THEN 45
             WHEN 'Email'             THEN 8
             ELSE 0
         END AS DOUBLE) / 100 AS touch_weight
FROM std s
LEFT JOIN stg_wholesalers w ON s.owner_email = w.email
LEFT JOIN stg_advisors a    ON s.contact_id = a.crm_contact_id
