-- severity: error
-- description: Every CRM activity has a known wholesaler and one of the four standard activity types.
SELECT activity_id FROM stg_activities WHERE wholesaler_id IS NULL OR activity_type = 'Other'
