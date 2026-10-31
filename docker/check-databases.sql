-- Run against the local Compose database. All test rows and tables are rolled back.
\set ON_ERROR_STOP on
\connect support
BEGIN;
SET LOCAL ROLE support_app;

INSERT INTO users (id, name, email, country, is_student, created_at)
VALUES ('u_schema_check', 'Schema Check', 'schema-check@example.com', 'UA', 0,
        '2026-10-31T14:00:00+02:00');
INSERT INTO payments (id, user_id, amount, kind, status, charged_at)
VALUES ('pay_schema_check', 'u_schema_check', 9.99, 'renewal', 'succeeded',
        '2026-10-31T12:00:00Z');
INSERT INTO retention_offers_used (user_id, offer_code, applied_at)
VALUES ('u_schema_check', 'discount_50_3m', '2026-10-31T12:00:00Z');

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM users WHERE id = 'u_schema_check'
                 AND created_at = TIMESTAMPTZ '2026-10-31T12:00:00Z') THEN
    RAISE EXCEPTION 'Timestamp did not preserve the UTC instant';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM payments WHERE id = 'pay_schema_check'
                 AND amount = 9.99::numeric) THEN
    RAISE EXCEPTION 'Monetary value did not round-trip';
  END IF;
  BEGIN
    INSERT INTO payments (id, user_id, amount, kind, status, charged_at)
    VALUES ('pay_invalid_reference', 'u_missing', 9.99, 'renewal', 'succeeded', now());
    RAISE EXCEPTION 'Missing foreign key was accepted';
  EXCEPTION WHEN foreign_key_violation THEN
    NULL;
  END;
END $$;

SET LOCAL ROLE support_reader;
SELECT count(*) AS readable_users FROM users;
DO $$
BEGIN
  BEGIN
    UPDATE users SET name = 'Unauthorized change' WHERE id = 'u_schema_check';
    RAISE EXCEPTION 'Read-only role was allowed to modify support data';
  EXCEPTION WHEN insufficient_privilege THEN
    NULL;
  END;
  IF has_database_privilege(current_user, 'analytics', 'CONNECT') THEN
    RAISE EXCEPTION 'Support reader can connect to analytics';
  END IF;
END $$;
ROLLBACK;

\connect analytics
BEGIN;
SET LOCAL ROLE analytics_app;
CREATE TABLE schema_permission_check (session_id TEXT PRIMARY KEY);
INSERT INTO schema_permission_check VALUES ('ses_schema_check');
DO $$
BEGIN
  IF has_database_privilege(current_user, 'support', 'CONNECT') THEN
    RAISE EXCEPTION 'Analytics writer can connect to support';
  END IF;
END $$;
ROLLBACK;
SELECT 'Database schema and permissions checks passed' AS result;
