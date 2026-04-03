-- init-db.sql — Create application schema alongside n8n's schema
-- Runs once when PostgreSQL container is first created.
-- n8n creates its own tables; this script adds the backend's app schema.

-- Separate schema to avoid collisions with n8n tables
CREATE SCHEMA IF NOT EXISTS app;

-- Allow the n8n/backend user to use the app schema
GRANT USAGE ON SCHEMA app TO CURRENT_USER;
GRANT CREATE ON SCHEMA app TO CURRENT_USER;

-- Note: Alembic migrations (run via 'make db-migrate') create the actual tables.
-- This script only ensures the schema exists so migrations can run.
