-- severity: error
-- description: Rep-level positions for a fund-month never exceed the fund's total AUM at the transfer agent.
SELECT p.product_code, p.month_key
FROM (SELECT product_code, month_key, SUM(market_value) AS mv FROM fct_positions GROUP BY product_code, month_key) p
JOIN stg_ta_flows t ON p.product_code = t.product_code AND p.month_key = t.month_key
WHERE p.mv > t.ending_aum * 1.001 + 1
