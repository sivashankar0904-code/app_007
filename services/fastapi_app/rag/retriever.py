"""
RAG retriever — vector similarity search against pgvector.

Given a user's question, find the most relevant chunks from the knowledge base.
These chunks are passed to the LLM as context to generate a grounded answer.

WHY cosine similarity (not L2/euclidean):
  Cosine measures the angle between vectors, not raw distance.
  For sentence embeddings, two sentences can have very different lengths
  but similar meaning — cosine handles this correctly. L2 would penalise length.

WHY top-k chunks (not the full document):
  LLMs have context window limits. Sending only the top 5 relevant chunks
  keeps the prompt focused and within token limits.
"""
import logging

import asyncio

from sqlalchemy import select, text

from config import get_settings
from rag.db import get_session_factory
from rag.models import DocumentChunk

logger = logging.getLogger(__name__)

TOP_K = 5  # number of chunks to return per query


async def _embed_query(query: str) -> list[float]:
    """
    Embed a single query — must use the same model as ingest time.
    WHY same model: query and chunk vectors must live in the same embedding space.
    Importing from ingestor keeps the singleton in one place (no duplicate model load).
    """
    from rag.ingestor import _get_embedding_model
    model = _get_embedding_model()
    loop = asyncio.get_event_loop()
    vector = await loop.run_in_executor(
        None, lambda: model.encode([query], convert_to_numpy=True)[0].tolist()
    )
    return vector


async def retrieve(
    query: str,
    org_id: int,
    chat_id: int | None = None,
    doc_id: int | None = None,
    top_k: int = TOP_K,
) -> list[dict]:
    """
    Embed the query, run cosine similarity search in pgvector, return top-k chunks.

    Args:
        query:   The user's natural language question.
        org_id:  Tenant scope — NEVER query without this (multi-tenancy boundary).
        chat_id: Optional — restrict search to a specific chat's documents.
        doc_id:  Optional — restrict search to a specific document.
        top_k:   How many chunks to return.

    Returns:
        List of dicts: { content, doc_id, chunk_index, score }
        Ordered by relevance (most relevant first).
    """
    # 1. Embed the query using the same model used at ingest time
    #    WHY same model: query and chunk vectors must be in the same embedding space.
    #    Mixing models = garbage similarity scores.
    query_vector = await _embed_query(query)

    # 2. pgvector cosine similarity search
    #    <=> operator = cosine distance (lower = more similar)
    #    1 - distance = similarity score (higher = better)
    session_factory = get_session_factory()
    async with session_factory() as session:
        # Build query with optional filters
        stmt = (
            select(
                DocumentChunk,
                (1 - DocumentChunk.embedding.cosine_distance(query_vector)).label("score"),
            )
            .where(DocumentChunk.org_id == org_id)
            .order_by(text("score DESC"))
            .limit(top_k)
        )

        if chat_id is not None:
            stmt = stmt.where(DocumentChunk.chat_id == chat_id)

        if doc_id is not None:
            stmt = stmt.where(DocumentChunk.doc_id == doc_id)

        result = await session.execute(stmt)
        rows = result.all()

    chunks = [
        {
            "content":     row.DocumentChunk.content,
            "doc_id":      row.DocumentChunk.doc_id,
            "chunk_index": row.DocumentChunk.chunk_index,
            "score":       round(float(row.score), 4),
        }
        for row in rows
    ]

    logger.info(
        f"[Retriever] query='{query[:50]}' org={org_id} → {len(chunks)} chunks returned"
    )
    return chunks


def format_context(chunks: list[dict]) -> str:
    """
    Format retrieved chunks into a single context string for the LLM prompt.
    Each chunk is labelled with its source doc and chunk index.
    """
    if not chunks:
        return "No relevant content found in the knowledge base."

    parts = []
    for i, chunk in enumerate(chunks, start=1):
        parts.append(
            f"[Source {i} — doc_id={chunk['doc_id']}, "
            f"chunk={chunk['chunk_index']}, score={chunk['score']}]\n"
            f"{chunk['content']}"
        )
    return "\n\n---\n\n".join(parts)
