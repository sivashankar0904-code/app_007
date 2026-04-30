# WHY pgvector/pgvector:pg16 instead of building from source:
#   Building pgvector from source (git clone + make) is fragile — the compiled
#   .so can have linking issues against the exact postgres binary in the image,
#   causing the postgres backend to crash on CREATE EXTENSION.
#   The official pgvector image ships a pre-built, tested binary that is
#   guaranteed to work with that exact postgres version.
FROM pgvector/pgvector:pg16

# pgvector extension will be enabled per-database via:
#   1. init.sql (fresh containers) — auto-run by docker-entrypoint-initdb.d/
#   2. Manual: docker compose exec postgres psql -U app007 -d app007 -c "CREATE EXTENSION IF NOT EXISTS vector;"
