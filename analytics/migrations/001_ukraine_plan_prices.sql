-- Update current catalog attributes while preserving dimension keys and financial facts.
BEGIN;
DO $$
BEGIN
  IF (SELECT count(*) FROM dim_plan WHERE plan_code IN ('individual','duo','family','student')) <> 4 THEN
    RAISE EXCEPTION 'Initialize analytics/schema.sql before applying the plan-price update';
  END IF;
END $$;
UPDATE dim_plan AS p
SET monthly_price = catalog.monthly_price
FROM (VALUES
  ('individual', 4.99::NUMERIC(10,2)),
  ('duo', 6.49::NUMERIC(10,2)),
  ('family', 7.99::NUMERIC(10,2)),
  ('student', 2.49::NUMERIC(10,2))
) AS catalog(plan_code, monthly_price)
WHERE p.plan_code = catalog.plan_code AND p.monthly_price IS DISTINCT FROM catalog.monthly_price;
COMMIT;
