"""
AI Service — FastAPI entry point.

Responsibilities:
- Expose internal AI endpoints (not public-facing)
- Start Redis Stream consumer on startup (listens to ai:events)
- LLM, RAG, and agentic workflows live here

WHY FastAPI: async-first, native streaming support for LLM tokens,
             automatic OpenAPI docs, great for internal service APIs.
"""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from consumers.stream_consumer import AIStreamConsumer
from routers import agents, health, rag


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup:
      1. Create pgvector table + extension if not exists
      2. Begin consuming Redis Stream (ai:events)
    Shutdown: cancel the consumer task cleanly.
    """
    # Create document_chunks table + pgvector extension (idempotent)
    from rag.db import create_tables
    await create_tables()

    consumer = AIStreamConsumer()
    task = asyncio.create_task(consumer.run())

    yield  # App is running

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="AI Service",
    description="Internal AI service — LLM, RAG, agentic workflows",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(agents.router, prefix="/agents")
app.include_router(rag.router, prefix="/rag")
