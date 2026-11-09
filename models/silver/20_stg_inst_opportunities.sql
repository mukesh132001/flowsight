-- Institutional RFP pipeline: one row per opportunity per stage reached.
SELECT
    opp_id,
    client_name,
    client_type,
    product_code,
    CAST(mandate_size_usd AS DOUBLE) AS mandate_size_usd,
    owner_id,
    stage,
    CASE stage WHEN 'Identified' THEN 1 WHEN 'RFP Issued' THEN 2 WHEN 'Finalist' THEN 3 ELSE 4 END AS stage_order,
    CAST(SUBSTR(stage_date, 1, 4)   || SUBSTR(stage_date, 6, 2)   AS INTEGER) AS stage_month_key,
    CAST(SUBSTR(created_date, 1, 4) || SUBSTR(created_date, 6, 2) AS INTEGER) AS created_month_key
FROM raw_inst_opportunities
