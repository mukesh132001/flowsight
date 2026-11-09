-- Transfer-agent control totals by fund and month: the book of record for flows and AUM.
-- inst_* columns split out institutional mandates (not visible in intermediary feeds).
SELECT
    product_code,
    CAST(SUBSTR(month_end, 1, 4) || SUBSTR(month_end, 6, 2) AS INTEGER) AS month_key,
    CAST(gross_sales AS DOUBLE) AS gross_sales,
    CAST(redemptions AS DOUBLE) AS redemptions,
    CAST(inst_gross_sales AS DOUBLE) AS inst_gross_sales,
    CAST(inst_redemptions AS DOUBLE) AS inst_redemptions,
    CAST(ending_aum AS DOUBLE)  AS ending_aum
FROM raw_ta_fund_flows
