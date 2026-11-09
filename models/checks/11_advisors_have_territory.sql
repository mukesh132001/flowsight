-- severity: error
-- description: Every advisor's branch state maps to a sales territory.
SELECT advisor_key FROM stg_advisors WHERE territory_code IS NULL OR channel IS NULL
