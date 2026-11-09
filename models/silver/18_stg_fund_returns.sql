SELECT
    product_code,
    CAST(SUBSTR(month_end, 1, 4) || SUBSTR(month_end, 6, 2) AS INTEGER) AS month_key,
    CAST(total_return AS DOUBLE)        AS total_return,
    CAST(category_avg_return AS DOUBLE) AS category_avg_return
FROM raw_fund_returns
