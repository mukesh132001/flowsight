-- Distribution partners (broker-dealers, RIAs, banks). firm_name_key is used to match
-- vendor B, which sends firm *names* with inconsistent case and trailing spaces.
SELECT
    firm_id,
    TRIM(firm_name)        AS firm_name,
    UPPER(TRIM(firm_name)) AS firm_name_key,
    channel,
    CASE WHEN channel IN ('Independent BD', 'RIA') THEN 'IR' ELSE 'WH' END AS channel_group,
    hq_state,
    data_vendor
FROM raw_firms
