SELECT
    wholesaler_id,
    quarter AS quarter_label,
    CAST(goal_gross_sales_usd AS DOUBLE) AS goal_gross_sales_usd
FROM raw_sales_goals
