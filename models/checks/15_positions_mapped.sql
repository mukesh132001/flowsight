-- severity: error
-- description: Every position's rep code maps to an advisor for its month.
SELECT rep_code, month_key FROM fct_positions WHERE advisor_key IS NULL
