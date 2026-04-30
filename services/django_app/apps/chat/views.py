"""
Chat views — internal bot-message endpoint.

POST /api/chat/bot-message/
  Called by FastAPI after generating a document summary.
  Saves the bot message to DB and broadcasts it to the chat room
  via Django Channels so all connected users see it in real time.

WHY an internal HTTP endpoint (not Redis Stream directly):
  FastAPI can't write to Django Channels' channel layer directly —
  the serialisation format is internal to channels-redis.
  An HTTP endpoint is simple, debuggable, and keeps the boundary clean.
  Secured with a shared INTERNAL_API_KEY — never exposed publicly.
"""
import json

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.http import JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from .models import Chat, Message


@method_decorator(csrf_exempt, name="dispatch")
class BotMessageView(View):
    """
    POST /api/chat/bot-message/

    Headers:
      X-Internal-Key: <INTERNAL_API_KEY>

    Body (JSON):
      { "chat_id": 1, "content": "Summary of the document..." }

    Flow:
      1. Validate internal key — reject if wrong
      2. Save Message to DB with sender_type=BOT
      3. Broadcast to WebSocket group via channel layer
      4. All connected users see the bot message instantly
    """

    def post(self, request):
        # ── Auth: shared secret between Django and FastAPI ───────────────────
        key = request.headers.get("X-Internal-Key", "")
        if key != settings.INTERNAL_API_KEY:
            return JsonResponse({"error": "Forbidden"}, status=403)

        # ── Parse body ───────────────────────────────────────────────────────
        try:
            body = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        chat_id = body.get("chat_id")
        content = body.get("content", "").strip()

        if not chat_id or not content:
            return JsonResponse({"error": "chat_id and content required"}, status=400)

        # ── Save bot message to DB ───────────────────────────────────────────
        try:
            chat = Chat.objects.get(id=chat_id)
        except Chat.DoesNotExist:
            return JsonResponse({"error": f"Chat {chat_id} not found"}, status=404)

        Message.objects.create(
            chat=chat,
            org_id=chat.org_id,
            sender=None,                      # no human sender
            sender_type=Message.SenderType.BOT,
            content=content,
        )

        # ── Broadcast via channel layer → WebSocket → all users in room ──────
        # WHY async_to_sync: channel layer is async, Django view is sync
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"chat_{chat_id}",
            {
                "type":    "chat.message",   # maps to ChatConsumer.chat_message()
                "sender":  "AI Assistant",
                "message": content,
                "is_bot":  True,
            },
        )

        return JsonResponse({"status": "ok"})
