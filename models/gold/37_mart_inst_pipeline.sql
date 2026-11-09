-- indexes: (month_key)
-- Institutional pipeline snapshot: the stage each opportunity was in at every month-end.
WITH opps AS (
    SELECT DISTINCT opp_id, created_month_key FROM stg_inst_opportunities
),
opp_months AS (
    SELECT o.opp_id, m.month_key, m.month_index
    FROM opps o
    JOIN dim_month m ON m.month_key >= o.created_month_key
),
stage_asof AS (
    SELECT om.opp_id, om.month_key, om.month_index, s.stage, s.stage_month_key,
           s.mandate_size_usd, s.product_code, s.client_type, s.client_name, s.owner_id,
           ROW_NUMBER() OVER (PARTITION BY om.opp_id, om.month_key
                              ORDER BY s.stage_month_key DESC, s.stage_order DESC) AS rn
    FROM opp_months om
    JOIN stg_inst_opportunities s ON om.opp_id = s.opp_id AND s.stage_month_key <= om.month_key
)
SELECT
    opp_id,
    month_key,
    month_index,
    stage,
    stage_month_key,
    client_name,
    client_type,
    product_code,
    owner_id,
    mandate_size_usd,
    CAST(CASE stage WHEN 'Identified' THEN 10 WHEN 'RFP Issued' THEN 25
                    WHEN 'Finalist' THEN 50 WHEN 'Won' THEN 100 ELSE 0 END AS DOUBLE) / 100 AS stage_probability,
    CASE WHEN stage IN ('Won', 'Lost', 'Withdrawn') THEN 0 ELSE 1 END            AS is_open,
    CASE WHEN stage IN ('Won', 'Lost') AND stage_month_key = month_key THEN 1 ELSE 0 END AS decided_this_month,
    CASE WHEN stage = 'Won' AND stage_month_key = month_key THEN 1 ELSE 0 END   AS won_this_month
FROM stage_asof
WHERE rn = 1
