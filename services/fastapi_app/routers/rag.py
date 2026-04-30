"""
RAG endpoints — document ingestion and vector search.

These are internal endpoints — called by Django or the Redis Stream consumer.
Not exposed publicly. Django is the public-facing API.

POST /rag/ingest — manually trigger ingestion (useful for retries)
POST /rag/query  — vector search + LLM-generated answer
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from llm.provider import get_cached_llm
from rag.ingestor import ingest_document
from rag.retriever import format_context, retrieve

router = APIRouter(tags=["rag"])


# ── Request/Response models ───────────────────────────────────────────────────

class IngestRequest(BaseModel):
    doc_id:    int
    org_id:    int
    chat_id:   int
    file_path: str   # relative path e.g. "documents/2024/01/file.pdf"


class QueryRequest(BaseModel):
    query:   str
    org_id:  int
    chat_id: int | None = None
    doc_id:  int | None = None


class QueryResponse(BaseModel):
    answer:  str
    sources: list[dict]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/ingest")
async def ingest(payload: IngestRequest):
    """
    Trigger RAG ingestion for a document.
    Normally called by the Redis Stream consumer automatically on upload.
    This endpoint exists for manual retries and testing.
    """
    try:
        chunks_stored = await ingest_document(
            doc_id=payload.doc_id,
            org_id=payload.org_id,
            chat_id=payload.chat_id,
            file_path_relative=payload.file_path,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {e}")

    return {"status": "ok", "doc_id": payload.doc_id, "chunks_stored": chunks_stored}


@router.post("/query", response_model=QueryResponse)
async def query(payload: QueryRequest):
    """
    Vector search + LLM-generated answer (RAG).

    Flow:
      1. Embed the query
      2. Retrieve top-k relevant chunks from pgvector
      3. Build a prompt: [context chunks] + [user question]
      4. LLM generates a grounded answer
      5. Return answer + sources

    WHY return sources:
      Transparency — the user can verify which document the answer came from.
      Prevents hallucination by grounding the answer in real retrieved content.
    """
    # 1. Retrieve relevant chunks
    chunks = await retrieve(
        query=payload.query,
        org_id=payload.org_id,
        chat_id=payload.chat_id,
        doc_id=payload.doc_id,
    )

    context = format_context(chunks)

    # 2. Build prompt — context + question
    prompt = (
        "You are a helpful assistant answering questions about documents "
        "shared in a collaborative chat thread.\n\n"
        "Use ONLY the context below to answer. "
        "If the answer is not in the context, say 'I could not find this in the documents.'\n\n"
        f"Context:\n{context}\n\n"
        f"Question: {payload.query}\n\n"
        "Answer:"
    )

    # 3. Generate answer
    llm = get_cached_llm()
    response = await llm.ainvoke(prompt)
    answer = response.content.strip()

    return QueryResponse(answer=answer, sources=chunks)
