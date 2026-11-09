-- indexes: (advisor_key, month_key) (product_code, month_key) (month_key)
-- One row per trade from either vendor, mapped to an advisor through the rep-code
-- crosswalk (valid for the trade month). Unmapped trades stay in, flagged.
WITH unioned AS (
    SELECT source_vendor, trade_id, trade_date, report_date, rep_code, firm_id, product_code,
           gross_sales, redemptions, was_corrected
    FROM stg_trades_vendor_a
    UNION ALL
    SELECT source_vendor, trade_id, trade_date, report_date, rep_code, firm_id, product_code,
           gross_sales, redemptions, was_corrected
    FROM stg_trades_vendor_b
),
keyed AS (
    SELECT u.*,
           CAST(SUBSTR(trade_date, 1, 4)  || SUBSTR(trade_date, 6, 2)  AS INTEGER) AS month_key,
           CAST(SUBSTR(report_date, 1, 4) || SUBSTR(report_date, 6, 2) AS INTEGER) AS report_month_key
    FROM unioned u
)
SELECT
    k.trade_id,
    k.source_vendor,
    k.trade_date,
    k.month_key,
    k.report_month_key,
    CASE WHEN k.report_month_key > k.month_key THEN 1 ELSE 0 END AS is_late,
    k.rep_code,
    x.advisor_key,
    CASE WHEN x.advisor_key IS NULL THEN 0 ELSE 1 END             AS is_mapped,
    k.firm_id,
    f.channel,
    f.channel_group,
    k.product_code,
    p.family_code,
    k.gross_sales,
    k.redemptions,
    k.gross_sales - k.redemptions AS net_flows,
    k.was_corrected
FROM keyed k
LEFT JOIN stg_rep_xref x
       ON k.rep_code = x.rep_code
      AND k.month_key BETWEEN x.start_month_key AND x.end_month_key
LEFT JOIN stg_firms f    ON k.firm_id = f.firm_id
LEFT JOIN stg_products p ON k.product_code = p.product_code
