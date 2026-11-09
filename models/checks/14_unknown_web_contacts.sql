-- severity: warn
-- description: Months where more than 5% of web events come from e-mails not in the advisor master (prospects).
SELECT month_key, AVG(CAST(1 - is_known_contact AS DOUBLE)) AS unknown_share
FROM fct_web_events
GROUP BY month_key
HAVING AVG(CAST(1 - is_known_contact AS DOUBLE)) > 0.05
