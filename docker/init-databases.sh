#!/bin/bash
set -euo pipefail

# The official image runs this script only when initializing an empty volume.
psql --username "$POSTGRES_USER" --dbname postgres --set ON_ERROR_STOP=1 \
  --set support_password="$SUPPORT_DB_PASSWORD" \
  --set reader_password="$SUPPORT_READONLY_PASSWORD" \
  --set analytics_password="$ANALYTICS_DB_PASSWORD" <<'SQL'
CREATE ROLE support_app LOGIN PASSWORD :'support_password';
CREATE ROLE support_reader LOGIN PASSWORD :'reader_password';
CREATE ROLE analytics_app LOGIN PASSWORD :'analytics_password';

CREATE DATABASE support OWNER support_app;
CREATE DATABASE analytics OWNER analytics_app;

\connect support
REVOKE CONNECT ON DATABASE support FROM PUBLIC;
GRANT CONNECT ON DATABASE support TO support_app, support_reader;
SET ROLE support_app;
\i /schema.sql
GRANT USAGE ON SCHEMA public TO support_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO support_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO support_reader;
RESET ROLE;

\connect analytics
REVOKE CONNECT ON DATABASE analytics FROM PUBLIC;
GRANT CONNECT ON DATABASE analytics TO analytics_app;
SET ROLE analytics_app;
\i /analytics-schema.sql
RESET ROLE;
SQL
