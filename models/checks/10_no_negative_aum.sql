-- severity: error
-- description: No fund ever shows negative AUM.
SELECT product_code, month_key FROM stg_ta_flows WHERE ending_aum < 0
