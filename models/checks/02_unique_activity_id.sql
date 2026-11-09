-- severity: error
-- description: Every CRM activity appears once after removing duplicate syncs.
SELECT activity_id FROM stg_activities GROUP BY activity_id HAVING COUNT(*) > 1
