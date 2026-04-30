"""
Document signals — post_save publishes to Redis Stream (ai:events).

Flow:
  Document.save() → post_save fires → publish to Redis Stream
  FastAPI consumer reads the stream → triggers RAG ingestion

WHY signals and not calling FastAPI directly in the view:
  1. Decoupling — the view doesn't know FastAPI exists
  2. Reliability — Redis Streams persist messages; FastAPI can be down
  3. Fan-out ready — multiple consumers can read the same stream later
     (e.g. audit logger, analytics)

WHY sync Redis publish (not async):
  Django signals are synchronous. The publish is fast (< 1ms).
  No need for async here — we're not waiting for a response.
"""
import json
import logging

import redis
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Document

logger = logging.getLogger(__name__)

# Sync Redis client — reused across signal calls (module-level = singleton)
# WHY sync: Django signals are sync; redis-py sync client is appropriate here
_redis = redis.from_url(settings.REDIS_URL, decode_responses=True)

STREAM_KEY = "ai:events"


@receiver(post_save, sender=Document)
def on_document_saved(sender, instance: Document, created: bool, **kwargs):
    """
    Fires after every Document.save().
    On creation only: publish event to Redis Stream so FastAPI ingests the file.

    WHY `created` check:
      Status updates (pending → processing → ready) also trigger post_save.
      Without this check, we'd re-ingest the document on every status change.
    """
    if not created:
        return

    payload = {
        "doc_id":    instance.id,
        "org_id":    instance.org_id,
        "chat_id":   instance.chat_id,
        "file_path": instance.file.name,   # relative path e.g. documents/2024/01/file.pdf
        "file_name": instance.file.name.split("/")[-1],
    }

    try:
        _redis.xadd(
            STREAM_KEY,
            {
                "event_type": "document.uploaded",
                "payload":    json.dumps(payload),
            },
        )
        logger.info(f"[Signal] Published document.uploaded | doc_id={instance.id}")
    except Exception as e:
        # WHY catch-all here: a failed Redis publish must never crash the upload request.
        # The document is already saved. Worst case: AI doesn't process it.
        # TODO: add retry via Celery task for resilience
        logger.error(f"[Signal] Failed to publish to Redis Stream: {e}")
