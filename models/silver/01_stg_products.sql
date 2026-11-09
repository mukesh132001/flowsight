-- Fund line-up: one row per fund (product_code).
SELECT
    TRIM(product_code)                         AS product_code,
    TRIM(fund_name)                            AS fund_name,
    vehicle,
    asset_class,
    category,
    family_code,
    family_name,
    CAST(mgmt_fee_bps AS DOUBLE)               AS mgmt_fee_bps,
    CASE WHEN launch_date IS NULL THEN NULL
         ELSE CAST(SUBSTR(launch_date, 1, 4) || SUBSTR(launch_date, 6, 2) AS INTEGER)
    END                                        AS launch_month_key
FROM raw_products
