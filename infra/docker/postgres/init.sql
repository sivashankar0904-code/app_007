-- Enable pgvector extension for vector similarity search.
-- WHY here (not application startup): this runs once at DB initialisation,
-- before any app connects. No transaction-wrapping issues.
-- Runs automatically on first container start (docker-entrypoint-initdb.d/).
CREATE EXTENSION IF NOT EXISTS vector;
