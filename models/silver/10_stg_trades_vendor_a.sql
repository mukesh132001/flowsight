-- Vendor A (wirehouse / regional / bank). Cancel-and-rebill corrections arrive as a
-- negative row with the same trade_ref; netting by trade_ref removes the bad booking.
WITH netted AS (
    SELECT
        trade_ref,
        txn_type,
        MIN(trade_date)                     AS trade_date,
        MIN(report_date)                    AS report_date,
        MIN(TRIM(rep_code))                 AS rep_code,
        MIN(firm_code)                      AS firm_id,
        MIN(product_code)                   AS product_code,
        SUM(CAST(amount AS DOUBLE))         AS amount,
        SUM(CASE WHEN is_correction = 'Y' THEN 1 ELSE 0 END) AS correction_rows
    FROM raw_sales_vendor_a
    GROUP BY trade_ref, txn_type
)
SELECT
    'A'                 AS source_vendor,
    'A:' || trade_ref   AS trade_id,
    trade_date,
    report_date,
    rep_code,
    firm_id,
    product_code,
    CASE WHEN txn_type = 'PURCHASE'   THEN amount ELSE CAST(0 AS DOUBLE) END AS gross_sales,
    CASE WHEN txn_type = 'REDEMPTION' THEN amount ELSE CAST(0 AS DOUBLE) END AS redemptions,
    CASE WHEN correction_rows > 0 THEN 1 ELSE 0 END AS was_corrected
FROM netted
WHERE ABS(amount) >= 0.01
