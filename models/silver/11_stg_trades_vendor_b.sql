-- Vendor B (independent BD / RIA): different layout, US dates, "$1,234.50" text amounts,
-- firm names instead of IDs, share-class codes, and occasional re-sent rows.
WITH dedup AS (
    SELECT b.*, ROW_NUMBER() OVER (PARTITION BY row_id ORDER BY row_id) AS rn
    FROM raw_sales_vendor_b b
),
parsed AS (
    SELECT
        row_id,
        SUBSTR(trade_dt, 7, 4) || '-' || SUBSTR(trade_dt, 1, 2) || '-' || SUBSTR(trade_dt, 4, 2) AS trade_date,
        TRIM(rep_id)                                                    AS rep_code,
        UPPER(TRIM(firm_name))                                          AS firm_name_key,
        TRIM(share_class)                                               AS share_class_code,
        CAST(REPLACE(REPLACE(purchases, '$', ''), ',', '') AS DOUBLE)   AS purchases,
        CAST(REPLACE(REPLACE(redemptions, '$', ''), ',', '') AS DOUBLE) AS redemptions
    FROM dedup
    WHERE rn = 1
)
SELECT
    'B'               AS source_vendor,
    'B:' || p.row_id  AS trade_id,
    p.trade_date,
    p.trade_date      AS report_date,
    p.rep_code,
    f.firm_id,
    s.product_code,
    p.purchases       AS gross_sales,
    p.redemptions     AS redemptions,
    0                 AS was_corrected
FROM parsed p
LEFT JOIN stg_firms f         ON p.firm_name_key = f.firm_name_key
LEFT JOIN stg_share_classes s ON p.share_class_code = s.share_class_code
