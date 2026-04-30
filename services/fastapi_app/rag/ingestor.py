"""
RAG ingestor — text extraction → chunking → embedding → pgvector storage.

Called by the Redis Stream consumer when a document.uploaded event arrives.

Pipeline:
  1. Read file from shared media volume
  2. Extract raw text (PDF or plain text)
  3. Split into overlapping chunks
  4. Embed each chunk via HuggingFace Inference API (all-MiniLM-L6-v2)
  5. Insert chunks + vectors into pgvector (document_chunks table)

WHY chunking with overlap:
  LLMs have a context window limit. Splitting a 50-page PDF into one big string
  won't fit. We split into smaller chunks so each fits in the LLM context.
  Overlap (e.g. 50 tokens) prevents answers being cut across chunk boundaries.

WHY all-MiniLM-L6-v2:
  384-dim, fast, free on HF Inference API.
  Strong semantic understanding for document Q&A tasks.
  Used by thousands of production RAG systems.
"""
import logging
import os
from pathlib import Path

import asyncio

from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer

from config import get_settings
from rag.db import get_session_factory
from rag.models import DocumentChunk

logger = logging.getLogger(__name__)

# Shared media root — same volume mount as Django's MEDIA_ROOT
# Docker/K8s: both services mount /media from the same PVC
MEDIA_ROOT = os.getenv("MEDIA_ROOT", "/media")

# Chunk settings
CHUNK_SIZE    = 500   # characters per chunk
CHUNK_OVERLAP = 50    # overlap between consecutive chunks


# Module-level singleton — loaded once, reused across all requests.
# WHY singleton: loading a transformer model takes ~2s and ~200MB RAM.
# Loading per-request would be slow and wasteful.
_embedding_model: SentenceTransformer | None = None


def _get_embedding_model() -> SentenceTransformer:
    global _embedding_model
    if _embedding_model is None:
        # First call downloads ~90MB to HF cache — subsequent starts use cache.
        # WHY all-MiniLM-L6-v2: 384-dim, fast CPU inference, strong semantic quality.
        _embedding_model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    return _embedding_model


async def _embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Embed a batch of texts locally using sentence-transformers.

    WHY local (not HF Inference API):
      HF free serverless API only allows a curated set of models.
      all-MiniLM-L6-v2 returns 404 on the free tier.
      Local inference: ~90MB download once, then zero latency, zero API dependency.

    WHY run_in_executor:
      sentence-transformers encode() is synchronous (CPU-bound).
      Running it directly in an async function would block the event loop.
      run_in_executor offloads it to a thread pool — event loop stays free.
    """
    model = _get_embedding_model()
    loop = asyncio.get_event_loop()
    vectors = await loop.run_in_executor(
        None, lambda: model.encode(texts, convert_to_numpy=True).tolist()
    )
    return vectors


def _extract_text(file_path: Path) -> str:
    """
    Extract raw text from PDF or plain text file.

    WHY pypdf and not pdfplumber:
      pypdf is pure Python, lighter dependency.
      pdfplumber is better for tables but overkill for chat documents.
    """
    suffix = file_path.suffix.lower()

    if suffix == ".pdf":
        try:
            import pypdf
            reader = pypdf.PdfReader(str(file_path))
            return "\n".join(
                page.extract_text() or "" for page in reader.pages
            ).strip()
        except Exception as e:
            logger.error(f"PDF extraction failed for {file_path}: {e}")
            raise

    elif suffix in (".txt", ".md"):
        return file_path.read_text(encoding="utf-8", errors="ignore").strip()

    else:
        raise ValueError(f"Unsupported file type: {suffix}")


def _chunk_text(text: str) -> list[str]:
    """
    Split text into overlapping chunks using LangChain's splitter.

    WHY RecursiveCharacterTextSplitter:
      Tries to split on paragraph breaks first, then sentences, then words.
      Produces more semantically coherent chunks than a naive character split.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    return splitter.split_text(text)


async def ingest_document(
    doc_id: int,
    org_id: int,
    chat_id: int,
    file_path_relative: str,
) -> int:
    """
    Full ingestion pipeline for one document.

    Args:
        doc_id:              Django Document.id
        org_id:              tenant id
        chat_id:             which chat this doc belongs to
        file_path_relative:  relative path from Django (e.g. 'documents/2024/01/file.pdf')

    Returns:
        Number of chunks stored.
    """
    abs_path = Path(MEDIA_ROOT) / file_path_relative
    logger.info(f"Ingesting doc_id={doc_id} | path={abs_path}")

    if not abs_path.exists():
        raise FileNotFoundError(f"File not found at {abs_path}")

    # 1. Extract text
    text = _extract_text(abs_path)
    if not text:
        logger.warning(f"doc_id={doc_id} — extracted empty text, skipping")
        return 0

    # 2. Chunk
    chunks = _chunk_text(text)
    logger.info(f"doc_id={doc_id} — {len(chunks)} chunks created")

    # 3. Embed all chunks in one batch call (more efficient than one-by-one)
    vectors = await _embed_texts(chunks)

    # 4. Store in pgvector
    session_factory = get_session_factory()
    async with session_factory() as session:
        # Delete any previous chunks for this doc (safe re-ingest)
        from sqlalchemy import delete
        await session.execute(
            delete(DocumentChunk).where(DocumentChunk.doc_id == doc_id)
        )

        chunk_rows = [
            DocumentChunk(
                doc_id=doc_id,
                org_id=org_id,
                chat_id=chat_id,
                chunk_index=i,
                content=chunk,
                embedding=vector,
            )
            for i, (chunk, vector) in enumerate(zip(chunks, vectors))
        ]
        session.add_all(chunk_rows)
        await session.commit()

    logger.info(f"doc_id={doc_id} — ingestion complete, {len(chunks)} chunks stored")
    return len(chunks)
