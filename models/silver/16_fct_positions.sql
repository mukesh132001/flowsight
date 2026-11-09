-- indexes: (advisor_key, month_key) (month_key)
-- Month-end assets by rep code and fund, mapped to advisors.
WITH pos AS (
    SELECT
        CAST(SUBSTR(as_of_date, 1, 4) || SUBSTR(as_of_date, 6, 2) AS INTEGER) AS month_key,
        TRIM(rep_code)                 AS rep_code,
        firm_id,
        product_code,
        CAST(market_value AS DOUBLE)   AS market_value
    FROM raw_positions_monthly
)
SELECT
    p.month_key,
    p.rep_code,
    x.advisor_key,
    p.firm_id,
    p.product_code,
    pr.family_code,
    p.market_value
FROM pos p
LEFT JOIN stg_rep_xref x
       ON p.rep_code = x.rep_code
      AND p.month_key BETWEEN x.start_month_key AND x.end_month_key
LEFT JOIN stg_products pr ON p.product_code = pr.product_code
