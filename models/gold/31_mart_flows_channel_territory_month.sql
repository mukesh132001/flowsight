-- indexes: (month_key)
-- Intermediary-reported flows by channel and territory. Trades whose rep code could not
-- be mapped to an advisor have no territory: they land in 'UNATTRIBUTED'.
SELECT
    t.month_key,
    t.channel,
    COALESCE(a.territory_code, 'UNATTRIBUTED') AS territory_code,
    t.family_code,
    SUM(t.gross_sales) AS gross_sales,
    SUM(t.redemptions) AS redemptions,
    SUM(t.net_flows)   AS net_flows,
    COUNT(DISTINCT CASE WHEN t.gross_sales > 0 THEN t.advisor_key END) AS producing_advisors
FROM fct_trades t
LEFT JOIN stg_advisors a ON t.advisor_key = a.advisor_key
GROUP BY t.month_key, t.channel, COALESCE(a.territory_code, 'UNATTRIBUTED'), t.family_code
