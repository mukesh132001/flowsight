-- indexes: (month_key) (product_code, month_key)
-- Fund x month AUM bridge from the transfer agent:
--   ending AUM = beginning AUM + gross sales - redemptions + market effect
-- plus what the intermediary sales feeds saw (feed_gross) and could attribute (mapped_gross).
WITH ta AS (
    SELECT
        t.product_code,
        t.month_key,
        m.month_index,
        t.gross_sales,
        t.redemptions,
        t.inst_gross_sales,
        t.inst_redemptions,
        t.ending_aum,
        LAG(t.ending_aum) OVER (PARTITION BY t.product_code ORDER BY m.month_index) AS beginning_aum
    FROM stg_ta_flows t
    JOIN dim_month m ON t.month_key = m.month_key
),
feed AS (
    SELECT
        product_code,
        month_key,
        SUM(gross_sales) AS feed_gross,
        SUM(redemptions) AS feed_redemptions,
        SUM(CASE WHEN is_mapped = 1 THEN gross_sales ELSE 0 END) AS mapped_gross
    FROM fct_trades
    GROUP BY product_code, month_key
)
SELECT
    ta.product_code,
    p.fund_name,
    p.vehicle,
    p.asset_class,
    p.category,
    p.family_code,
    p.family_name,
    ta.month_key,
    ta.month_index,
    ta.beginning_aum,
    ta.gross_sales,
    ta.redemptions,
    ta.gross_sales - ta.redemptions                                     AS net_flows,
    ta.gross_sales - ta.inst_gross_sales                                AS intermediary_gross,
    ta.inst_gross_sales,
    ta.inst_redemptions,
    ta.ending_aum - ta.beginning_aum - (ta.gross_sales - ta.redemptions) AS market_effect,
    ta.ending_aum,
    ta.ending_aum * p.mgmt_fee_bps / 10000                              AS revenue_run_rate,
    COALESCE(f.feed_gross, 0)        AS feed_gross,
    COALESCE(f.feed_redemptions, 0)  AS feed_redemptions,
    COALESCE(f.mapped_gross, 0)      AS mapped_gross,
    r.total_return,
    r.category_avg_return,
    r.total_return - r.category_avg_return AS excess_return
FROM ta
JOIN stg_products p           ON ta.product_code = p.product_code
LEFT JOIN feed f              ON ta.product_code = f.product_code AND ta.month_key = f.month_key
LEFT JOIN stg_fund_returns r  ON ta.product_code = r.product_code AND ta.month_key = r.month_key
WHERE ta.beginning_aum IS NOT NULL
