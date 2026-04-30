"""
Chat views — internal bot-message endpoints.

POST /api/chat/bot-message/
  Called by FastAPI to post a bot message.
  Supports private delivery (to one user only) or public (broadcast to room).

POST /api/chat/share-message/
  Called by the frontend when user clicks "Share" on a private bot reply.
  Broadcasts the Q&A to all participants in the chat room.

WHY internal HTTP (not Redis Stream directly):
  FastAPI can't write to Django Channels' channel layer directly.
  HTTP is simple, debuggable, and keeps the boundary clean.
  Secured with INTERNAL_API_KEY — never exposed publicly.
"""
import json

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.http import JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

from .models import Chat, Message

User = get_user_model()


def _check_internal_key(request):
    key = request.headers.get("X-Internal-Key", "")
    return key == settings.INTERNAL_API_KEY


@method_decorator(csrf_exempt, name="dispatch")
class BotMessageView(View):
    """
    POST /api/chat/bot-message/

    Body (JSON):
      {
        "chat_id": 1,
        "content": "...",
        "private_to_user_id": 42   ← optional; omit to broadcast to all
      }

    If private_to_user_id is set:
      - Message is NOT saved to DB (ephemeral — only visible to that user)
      - Delivered to private_user_{id} channel group only
      - Frontend shows "Keep private" / "Share" buttons

    If private_to_user_id is absent:
      - Message IS saved to DB
      - Broadcast to all users in chat_{chat_id}
    """

    def post(self, request):
        if not _check_internal_key(request):
            return JsonResponse({"error": "Forbidden"}, status=403)

        try:
            body = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        chat_id            = body.get("chat_id")
        content            = body.get("content", "").strip()
        private_to_user_id = body.get("private_to_user_id")  # None = public
        question           = body.get("question", "")         # shown in private UI

        if not chat_id or not content:
            return JsonResponse({"error": "chat_id and content required"}, status=400)

        try:
            chat = Chat.objects.get(id=chat_id)
        except Chat.DoesNotExist:
            return JsonResponse({"error": f"Chat {chat_id} not found"}, status=404)

        channel_layer = get_channel_layer()

        if private_to_user_id:
            # ── Private delivery — only the asking user sees this ────────────
            # WHY no DB save: private messages are ephemeral.
            # If user shares, ShareMessageView persists and broadcasts it.
            async_to_sync(channel_layer.group_send)(
                f"private_user_{private_to_user_id}",
                {
                    "type":       "chat.message",
                    "sender":     "AI Assistant",
                    "message":    content,
                    "is_bot":     True,
                    "is_private": True,    # frontend shows action buttons
                    "question":   question,
                },
            )
        else:
            # ── Public broadcast — all users in the chat room see this ───────
            Message.objects.create(
                chat=chat,
                org_id=chat.org_id,
                sender=None,
                sender_type=Message.SenderType.BOT,
                content=content,
            )
            async_to_sync(channel_layer.group_send)(
                f"chat_{chat_id}",
                {
                    "type":    "chat.message",
                    "sender":  "AI Assistant",
                    "message": content,
                    "is_bot":  True,
                },
            )

        return JsonResponse({"status": "ok"})


@method_decorator(csrf_exempt, name="dispatch")
class ShareMessageView(View):
    """
    POST /api/chat/share-message/

    Called by the frontend when the user clicks "Share" on a private bot reply.
    Persists the Q&A to DB and broadcasts it to all chat participants.

    Body (JSON):
      { "chat_id": 1, "question": "who is the client?", "answer": "Acme Corp..." }
    """

    def post(self, request):
        """
        Authenticate via Bearer JWT (frontend) and share the private bot reply
        to the whole chat room.

        WHY manual JWT decode (not DRF APIView):
          BotMessageView is already a plain Django View (internal key auth).
          Keeping ShareMessageView consistent avoids mixing DRF + Django view
          base classes in the same file. simplejwt token validation is one call.
        """
        # ── Identify the sharing user from JWT ────────────────────────────────
        username = "User"
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            raw_token = auth_header.split(" ", 1)[1]
            try:
                token = AccessToken(raw_token)
                user  = User.objects.get(id=token["user_id"], is_active=True)
                username = user.username
            except (InvalidToken, TokenError, User.DoesNotExist):
                return JsonResponse({"error": "Invalid or expired token"}, status=401)
        else:
            return JsonResponse({"error": "Authorization header required"}, status=401)

        try:
            body = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        chat_id  = body.get("chat_id")
        question = body.get("question", "").strip()
        answer   = body.get("answer", "").strip()

        if not chat_id or not answer:
            return JsonResponse({"error": "chat_id and answer required"}, status=400)

        try:
            chat = Chat.objects.get(id=chat_id)
        except Chat.DoesNotExist:
            return JsonResponse({"error": f"Chat {chat_id} not found"}, status=404)

        # Format the shared Q&A as a single message
        if question:
            shared_content = f"💬 **{username} asked:** {question}\n\n{answer}"
        else:
            shared_content = answer

        # Save to DB so it persists for late joiners
        Message.objects.create(
            chat=chat,
            org_id=chat.org_id,
            sender=None,
            sender_type=Message.SenderType.BOT,
            content=shared_content,
        )

        # Broadcast to all users
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"chat_{chat_id}",
            {
                "type":    "chat.message",
                "sender":  "AI Assistant",
                "message": shared_content,
                "is_bot":  True,
            },
        )

        return JsonResponse({"status": "ok"})
