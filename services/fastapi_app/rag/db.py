"""
Async SQLAlchemy engine + session factory for the RAG service.

WHY async engine (not sync):
  FastAPI is async-first. Blocking the event loop with sync DB calls would
  kill concurrency — one slow query stalls all other requests.
  asyncpg + async SQLAlchemy keeps everything non-blocking.

WHY a single engine (module-level):
  Engine creation is expensive (connection pool setup).
  One engine shared across all requests = efficient connection pooling.
"""
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config import get_settings

_engine = None
_session_factory = None


def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.database_url,
            echo=False,       # set True to log SQL — useful for debugging
            pool_size=5,      # max persistent connections
            max_overflow=10,  # extra connections under burst load
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(),
            expire_on_commit=False,  # keep objects readable after commit
        )
    return _session_factory


async def create_tables():
    """
    Create the document_chunks table (with pgvector column) at FastAPI startup.

    WHY not Django migrations:
      FastAPI owns this table. Django migrations only run for Django-managed tables.
      SQLAlchemy create_all is the right tool here.

    WHY we do NOT create the pgvector extension here:
      CREATE EXTENSION triggers a backend-process reload in PostgreSQL. asyncpg
      sees the TCP connection drop mid-operation and raises ConnectionDoesNotExistError
      regardless of isolation level or whether we use raw asyncpg or SQLAlchemy.

      Extension setup belongs at database initialisation time, not application
      startup. Two places handle it:
        1. infra/docker/postgres/init.sql  — runs once on fresh container start
        2. One-time manual command for existing DBs:
           docker compose exec postgres psql -U app007 -d app007 \
             -c "CREATE EXTENSION IF NOT EXISTS vector;"
    """
    from rag.models import Base

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
