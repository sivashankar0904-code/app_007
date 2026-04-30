"""
SQLAlchemy async model — document_chunks table with pgvector.

WHY SQLAlchemy here (not Django ORM):
  FastAPI has no Django. It talks to the same PostgreSQL database directly
  via async SQLAlchemy. Django manages its own tables; FastAPI manages this one.

WHY a separate table (document_chunks) instead of storing in Django's documents table:
  One document = many chunks (paragraphs, pages).
  Each chunk has its own embedding vector.
  Vector search happens at chunk level — not document level.
  Storing all chunks in the documents table would bloat it and break the model.

Schema:
  document_chunks
    id          — serial PK
    doc_id      — matches Django's documents.id (no FK — cross-service boundary)
    org_id      — tenant scope (never query without this)
    chat_id     — which chat this doc belongs to
    chunk_index — order of chunk within the document
    content     — raw text of the chunk
    embedding   — vector(384) — all-MiniLM-L6-v2 output dimension
"""
from pgvector.sqlalchemy import Vector
from sqlalchemy import BigInteger, Column, Index, Integer, Text
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    doc_id      = Column(BigInteger, nullable=False, index=True)
    org_id      = Column(BigInteger, nullable=False, index=True)
    chat_id     = Column(BigInteger, nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    content     = Column(Text, nullable=False)

    # 384 dimensions = all-MiniLM-L6-v2 output size
    # WHY 384 and not 1536 (OpenAI): smaller = faster search, less storage,
    # still excellent semantic quality for document Q&A
    embedding   = Column(Vector(384), nullable=True)

    __table_args__ = (
        # IVFFlat index — approximate nearest neighbour (ANN) search
        # WHY not exact search: for 10k+ chunks, exact cosine search is O(n).
        # IVFFlat trades tiny accuracy loss for O(sqrt(n)) search speed.
        # lists=100 is a reasonable default; tune up for larger datasets.
        # NOTE: index created at DB init time via create_tables()
        Index(
            "ix_document_chunks_embedding",
            "embedding",
            postgresql_using="ivfflat",
            postgresql_with={"lists": 100},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )
