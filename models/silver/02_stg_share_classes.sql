-- Share-class crosswalk: vendor B reports share classes (AP-LCC-I), the rest of the
-- business works at fund level (AP-LCC).
SELECT
    TRIM(share_class_code) AS share_class_code,
    TRIM(product_code)     AS product_code,
    share_class
FROM raw_share_class_xref
