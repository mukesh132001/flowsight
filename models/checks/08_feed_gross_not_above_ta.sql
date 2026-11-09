-- severity: error
-- description: Intermediary feeds can never report more gross sales for a fund-month than the transfer agent's intermediary total (book of record).
SELECT product_code, month_key
FROM mart_product_month
WHERE feed_gross > intermediary_gross * 1.001 + 1
