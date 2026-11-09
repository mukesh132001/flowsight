-- Industry gross sales by fund category (market-share denominator).
SELECT
    category,
    CAST(SUBSTR(month_end, 1, 4) || SUBSTR(month_end, 6, 2) AS INTEGER) AS month_key,
    CAST(industry_gross_sales AS DOUBLE) AS industry_gross_sales
FROM raw_industry_flows
