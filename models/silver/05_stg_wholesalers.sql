-- Sales team. end_month_key = 999912 while the person is still in seat.
SELECT
    wholesaler_id,
    first_name || ' ' || last_name AS wholesaler_name,
    LOWER(TRIM(email))             AS email,
    role,
    territory_code,
    channel_group,
    CAST(SUBSTR(start_date, 1, 4) || SUBSTR(start_date, 6, 2) AS INTEGER) AS start_month_key,
    CASE WHEN end_date IS NULL THEN 999912
         ELSE CAST(SUBSTR(end_date, 1, 4) || SUBSTR(end_date, 6, 2) AS INTEGER)
    END AS end_month_key
FROM raw_wholesalers
