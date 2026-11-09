-- severity: error
-- description: Every trade maps to a fund (vendor B share-class codes resolve via the crosswalk).
SELECT trade_id FROM fct_trades WHERE product_code IS NULL OR family_code IS NULL
