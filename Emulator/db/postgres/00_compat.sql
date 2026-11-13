-- PostgreSQL helpers so the game database behaves as the 2008 server's SQL Server database did (session 42).
-- Applied before the tables (tools/pgport/migrate.py, db/postgres/setup).
CREATE EXTENSION IF NOT EXISTS citext;      -- text columns: SQL Server's default collation compared case-insensitively

-- SQL Server's clock functions (the containers run in UTC, as the SQL Server one did)
CREATE OR REPLACE FUNCTION getdate() RETURNS timestamp(3) LANGUAGE sql STABLE AS $$ SELECT localtimestamp(3) $$;
CREATE OR REPLACE FUNCTION getutcdate() RETURNS timestamp(3) LANGUAGE sql STABLE
  AS $$ SELECT (now() AT TIME ZONE 'utc')::timestamp(3) $$;
CREATE OR REPLACE FUNCTION sysdatetime() RETURNS timestamp LANGUAGE sql STABLE AS $$ SELECT localtimestamp $$;
CREATE OR REPLACE FUNCTION isnull(anycompatible, anycompatible) RETURNS anycompatible LANGUAGE sql IMMUTABLE
  AS $$ SELECT coalesce($1, $2) $$;
