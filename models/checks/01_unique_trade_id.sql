-- severity: error
-- description: Every trade appears once after de-duplication and correction netting.
SELECT trade_id FROM fct_trades GROUP BY trade_id HAVING COUNT(*) > 1
