-- Compute SuburbStats from the NSW Sales data already in `properties`.
-- One snapshot row per suburb, dated today, with:
--   median_price (overall) / _house / _unit
--   capital_growth_1yr / _3yr / _5yr  (percent change in median vs N years ago)
-- Idempotent via ON CONFLICT on (suburb_id, snapshot_date).

WITH yearly_medians AS (
  SELECT
    suburb_id,
    EXTRACT(YEAR FROM sold_at)::int AS yr,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY sold_price)::bigint AS median_price,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY sold_price)
      FILTER (WHERE property_type = 'house')::bigint AS median_house,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY sold_price)
      FILTER (WHERE property_type = 'apartment')::bigint AS median_unit,
    COUNT(*) AS sales_count
  FROM properties
  WHERE status = 'sold'
    AND sold_at IS NOT NULL
    AND sold_price IS NOT NULL
    AND sold_price BETWEEN 10000000 AND 2000000000   -- $100k–$20M, residential range
    AND suburb_id IS NOT NULL
    AND sold_at BETWEEN DATE '2020-01-01' AND CURRENT_DATE
  GROUP BY suburb_id, yr
),
suburb_summary AS (
  SELECT
    suburb_id,
    MAX(median_price) FILTER (WHERE yr = 2025) AS current_median,
    MAX(median_house) FILTER (WHERE yr = 2025) AS current_house,
    MAX(median_unit)  FILTER (WHERE yr = 2025) AS current_unit,
    MAX(median_price) FILTER (WHERE yr = 2024) AS y1_median,
    MAX(median_price) FILTER (WHERE yr = 2022) AS y3_median,
    MAX(median_price) FILTER (WHERE yr = 2020) AS y5_median,
    SUM(sales_count)                          AS total_sales
  FROM yearly_medians
  GROUP BY suburb_id
)
INSERT INTO suburb_stats (
  suburb_id, snapshot_date,
  median_price, median_price_house, median_price_unit,
  capital_growth_1yr, capital_growth_3yr, capital_growth_5yr,
  total_listings, source
)
SELECT
  suburb_id,
  CURRENT_DATE,
  current_median,
  current_house,
  current_unit,
  CASE WHEN y1_median > 0
       THEN ROUND(((current_median::numeric - y1_median) / y1_median * 100), 2)
       ELSE NULL END,
  CASE WHEN y3_median > 0
       THEN ROUND(((current_median::numeric - y3_median) / y3_median * 100), 2)
       ELSE NULL END,
  CASE WHEN y5_median > 0
       THEN ROUND(((current_median::numeric - y5_median) / y5_median * 100), 2)
       ELSE NULL END,
  total_sales,
  'derived_from_nsw_sales'
FROM suburb_summary
WHERE current_median IS NOT NULL
ON CONFLICT (suburb_id, snapshot_date) DO UPDATE SET
  median_price       = EXCLUDED.median_price,
  median_price_house = EXCLUDED.median_price_house,
  median_price_unit  = EXCLUDED.median_price_unit,
  capital_growth_1yr = EXCLUDED.capital_growth_1yr,
  capital_growth_3yr = EXCLUDED.capital_growth_3yr,
  capital_growth_5yr = EXCLUDED.capital_growth_5yr,
  total_listings     = EXCLUDED.total_listings;
