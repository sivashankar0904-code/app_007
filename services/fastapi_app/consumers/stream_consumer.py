"""
AIStreamConsumer — listens to the `ai:events` Redis Stream.

Django publishes events here (e.g. document uploaded).
This service consumes them and triggers the appropriate AI workflow.

WHY Redis Streams: persistent, ordered, consumer-group aware.
                   Unlike pub/sub, messages survive if the consumer is down.
"""
import asyncio
import json
import logging
from pathlib import Path

import httpx
import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

STREAM_KEY = "ai:events"
CONSUMER_GROUP = "ai-service"
CONSUMER_NAME = "ai-worker-1"


class AIStreamConsumer:
    def __init__(self, redis_url: str = "redis://redis:6379/0"):
        self.redis_url = redis_url
        self.client: aioredis.Redis | None = None

    async def _ensure_group(self):
        """Create consumer group if it doesn't exist yet."""
        try:
            await self.client.xgroup_create(STREAM_KEY, CONSUMER_GROUP, id="0", mkstream=True)
        except Exception:
            pass  # Group already exists

    async def run(self):
        self.client = aioredis.from_url(self.redis_url)
        await self._ensure_group()
        logger.info(f"Listening on stream: {STREAM_KEY}")

        while True:
            try:
                messages = await self.client.xreadgroup(
                    groupname=CONSUMER_GROUP,
                    consumername=CONSUMER_NAME,
                    streams={STREAM_KEY: ">"},
                    count=10,
                    block=5000,  # block 5s, then loop
                )
                for _, entries in (messages or []):
                    for msg_id, fields in entries:
                        await self._handle(msg_id, fields)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Stream consumer error: {e}")
                await asyncio.sleep(2)

        await self.client.aclose()

    async def _handle(self, msg_id: bytes, fields: dict):
        event_type = fields.get(b"event_type", b"").decode()
        payload = json.loads(fields.get(b"payload", b"{}"))
        logger.info(f"Event: {event_type} | payload: {payload}")

        # Route to correct workflow
        if event_type == "document.uploaded":
            await self._on_document_uploaded(payload)
        elif event_type == "chat.question":
            await self._on_chat_question(payload)
        else:
            logger.warning(f"Unknown event type: {event_type}")

        # Acknowledge processed
        await self.client.xack(STREAM_KEY, CONSUMER_GROUP, msg_id)

    async def _on_document_uploaded(self, payload: dict):
        """
        Full pipeline for a document upload event:
          1. Ingest — extract text, chunk, embed, store in pgvector
          2. Summarise — LLM generates a concise document summary
          3. Post — send summary as bot message to the chat via Django internal API
        """
        from rag.ingestor import ingest_document, _extract_text
        from llm.provider import get_cached_llm
        from config import get_settings

        doc_id    = payload.get("doc_id")
        org_id    = payload.get("org_id")
        chat_id   = payload.get("chat_id")
        file_path = payload.get("file_path")
        file_name = payload.get("file_name", "document")

        logger.info(f"[Consumer] Starting pipeline for doc_id={doc_id}")

        # ── Step 1: Ingest (embed + store in pgvector) ────────────────────────
        try:
            chunks = await ingest_document(
                doc_id=doc_id,
                org_id=org_id,
                chat_id=chat_id,
                file_path_relative=file_path,
            )
            logger.info(f"[Consumer] doc_id={doc_id} — {chunks} chunks stored")
        except Exception as e:
            logger.error(f"[Consumer] Ingestion failed for doc_id={doc_id}: {e}")
            return  # no point summarising if ingestion failed

        # ── Step 2: Extractive summary (no LLM API needed) ───────────────────
        # WHY extractive (not LLM): HF free-tier serverless inference API does
        # not host 7B models — they return 404. Extractive summary is instant,
        # zero-dependency, and gives users the actual document content immediately.
        # LLM summary can be layered back in once we have a paid API key.
        try:
            settings = get_settings()
            abs_path = Path(settings.media_root) / file_path
            text = _extract_text(abs_path)

            # Split into sentences and take the first 5 meaningful ones
            import re
            sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if len(s.strip()) > 40]
            top_sentences = sentences[:5]

            if top_sentences:
                bullets = "\n".join(f"• {s}" for s in top_sentences)
                summary = f"📄 **{file_name}** — here's what I found:\n\n{bullets}\n\n_{chunks} chunks indexed and ready for questions._"
            else:
                summary = f"📄 **{file_name}** has been processed — {chunks} chunks indexed and ready for questions."

            logger.info(f"[Consumer] doc_id={doc_id} — extractive summary built ({len(top_sentences)} sentences)")

        except Exception as e:
            logger.error(f"[Consumer] Summary generation failed for doc_id={doc_id}: {e}")
            summary = f"📄 **{file_name}** has been processed and is ready for questions."

        # ── Step 3: Post summary to chat via Django internal API ──────────────
        # WHY HTTP and not Redis: Django Channels uses an internal Redis format
        # that's not safe to write to directly. HTTP is simple and reliable.
        try:
            settings = get_settings()
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"{settings.django_internal_url}/api/chat/bot-message/",
                    json={"chat_id": chat_id, "content": summary},
                    headers={"X-Internal-Key": settings.internal_api_key},
                )
                resp.raise_for_status()
            logger.info(f"[Consumer] doc_id={doc_id} — summary posted to chat_{chat_id}")

        except Exception as e:
            logger.error(f"[Consumer] Failed to post summary to chat: {e}")

    async def _on_chat_question(self, payload: dict):
        """
        RAG Q&A pipeline triggered when a user asks a question in the chat.

        Flow:
          1. Embed the question (sentence-transformers, local)
          2. Cosine similarity search in pgvector — top-k relevant chunks
          3. Format chunks into a readable answer
          4. Post answer as bot message via Django internal API

        WHY extractive (not LLM generation):
          HF free-tier serverless API does not host 7B models.
          Extractive RAG — returning the actual document text that answers
          the question — is honest, fast, and often more accurate than
          hallucination-prone generation. LLM layer can be added later.
        """
        from rag.retriever import retrieve, format_context
        from config import get_settings

        # Cast to int — Redis Stream values are bytes/strings;
        # JSON parses numbers correctly but guard defensively
        chat_id  = int(payload.get("chat_id"))
        org_id   = int(payload.get("org_id"))
        user_id  = int(payload.get("user_id"))
        question = payload.get("question", "")

        logger.info(f"[Consumer] RAG Q&A | chat={chat_id} | q={question[:80]}")

        try:
            chunks = await retrieve(
                query=question,
                org_id=org_id,
                chat_id=chat_id,
                top_k=3,
            )
        except Exception as e:
            logger.error(f"[Consumer] Retrieval failed: {e}")
            chunks = []

        # ── Format answer ─────────────────────────────────────────────────────
        if not chunks:
            answer = (
                f"🔍 I searched the uploaded documents but couldn't find "
                f"relevant information for: *{question}*\n\n"
                f"Try uploading a document first, then ask questions about it."
            )
        else:
            top = chunks[0]
            rest = chunks[1:] if len(chunks) > 1 else []

            # Use extracted answer sentences (pinpoint) not the full raw chunk
            lines = [f"🔍 **Based on the uploaded documents:**\n"]
            lines.append(top["answer"])

            if rest:
                lines.append("\n**Also relevant:**")
                for c in rest:
                    # Use extracted sentences for secondary results too
                    lines.append(f"• {c['answer']}")

            answer = "\n".join(lines)

        # ── Post privately to the asking user only ────────────────────────────
        # WHY private: the user gets a personal AI reply first.
        # They decide whether to keep it or share it with the group.
        try:
            settings = get_settings()
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"{settings.django_internal_url}/api/chat/bot-message/",
                    json={
                        "chat_id":            chat_id,
                        "content":            answer,
                        "private_to_user_id": user_id,   # private delivery
                        "question":           question,   # shown in UI above buttons
                    },
                    headers={"X-Internal-Key": settings.internal_api_key},
                )
                resp.raise_for_status()
            logger.info(f"[Consumer] RAG answer posted privately to user_{user_id}")
        except Exception as e:
            logger.error(f"[Consumer] Failed to post RAG answer: {e}")
