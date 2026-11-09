-- severity: error
-- description: Every trade maps to a firm (vendor B firm names resolve after trimming and upper-casing).
SELECT trade_id FROM fct_trades WHERE firm_id IS NULL OR channel IS NULL
