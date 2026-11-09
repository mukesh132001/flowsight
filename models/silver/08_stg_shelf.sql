-- Platform approvals: a fund can only be sold at a firm once it is on that firm's shelf.
SELECT
    firm_id,
    product_code,
    CASE WHEN approved_date IS NULL THEN NULL
         ELSE CAST(SUBSTR(approved_date, 1, 4) || SUBSTR(approved_date, 6, 2) AS INTEGER)
    END AS approved_month_key
FROM raw_platform_shelf
