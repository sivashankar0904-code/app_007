"""
ChatConsumer — WebSocket consumer for real-time chat.

Authentication:
  JWT token must be passed as a query parameter on connect:
  ws://localhost:8000/ws/chat/1/?token=<access_token>

  - Token is validated BEFORE accept() — unauthenticated clients get close code 4001
  - User is attached to self.user for use in receive/broadcast

RAG Q&A trigger:
  When a user's message looks like a question (contains '?' or starts with a
  question word), the consumer publishes a chat.question event to the ai:events
  Redis Stream. The FastAPI AI service consumes it, retrieves relevant document
  chunks from pgvector, and posts an answer back as a bot message.

  WHY Redis Stream (not direct HTTP to FastAPI):
    The consumer is async and must not block the WebSocket event loop waiting
    for an LLM response. Publishing to Redis is instant; FastAPI picks it up
    in its own consumer loop and responds when ready — fully decoupled.
"""
import json
import logging
import os
from urllib.parse import parse_qs

import redis.asyncio as aioredis
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import AccessToken

User = get_user_model()
logger = logging.getLogger(__name__)

REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")

# Words that signal a question even without a '?'
_QUESTION_STARTERS = {
    "what", "who", "how", "when", "where", "why",
    "explain", "summarize", "summarise", "tell", "describe",
    "is", "are", "does", "can", "could", "would", "should",
    "which", "show", "list", "find",
}


def _is_question(message: str) -> bool:
    """
    Heuristic: treat a message as a question if it contains '?' or starts
    with a recognised question word.

    WHY heuristic (not NLP): zero latency, zero dependency.
    Good enough for a collaborative AI thread demo.
    """
    text = message.strip().lower()
    if not text:
        return False
    if "?" in text:
        return True
    first_word = text.split()[0].rstrip(",.!;:")
    return first_word in _QUESTION_STARTERS


class ChatConsumer(AsyncWebsocketConsumer):

    # ── Auth helper ───────────────────────────────────────────────────────────

    @database_sync_to_async
    def _get_user(self, user_id):
        """Fetch active user by id — runs in a thread (ORM is sync)."""
        try:
            return User.objects.get(id=user_id, is_active=True)
        except User.DoesNotExist:
            return None

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def connect(self):
        # 1. Extract ?token= from query string
        qs = self.scope.get("query_string", b"").decode()
        params = parse_qs(qs)
        token_list = params.get("token", [])

        if not token_list:
            await self.close(code=4001)  # 4001 = missing token
            return

        # 2. Validate JWT
        try:
            access_token = AccessToken(token_list[0])
            user = await self._get_user(access_token["user_id"])
        except (InvalidToken, TokenError):
            await self.close(code=4001)  # 4001 = invalid token
            return

        if user is None:
            await self.close(code=4001)  # 4001 = user not found / inactive
            return

        # 3. Auth passed — set up state and accept
        self.user = user
        self.chat_id = self.scope["url_route"]["kwargs"]["chat_id"]
        self.group_name = f"chat_{self.chat_id}"

        # Private group — only this user's connections receive messages sent here.
        # WHY per-user group (not channel_name direct): channel_name changes on
        # reconnect; user_id is stable. Sending to this group reaches the user
        # even if they have multiple tabs open.
        self.private_group = f"private_user_{self.user.id}"

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.channel_layer.group_add(self.private_group, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
        if hasattr(self, "private_group"):
            await self.channel_layer.group_discard(self.private_group, self.channel_name)

    # ── Messaging ─────────────────────────────────────────────────────────────

    async def receive(self, text_data):
        """
        Receive message from WebSocket client.

        Flow:
          1. Validate + parse JSON
          2a. Regular message → broadcast to all users in the chat group
          2b. Question → send ONLY to the asking user's private group (held back
              from the room until they decide Keep / Share after seeing the answer)
          3. If message is a question → publish to ai:events for RAG answer

        WHY hold the question back:
          User A's question should stay invisible to User B until User A
          decides to share the AI reply. If we broadcast immediately, User B
          sees the question with no context and no answer yet — confusing.
          The question + answer pair are revealed together only on Share.
        """
        if not text_data or not text_data.strip():
            await self.send(text_data=json.dumps({"error": "Empty message"}))
            return

        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps(
                {"error": "Invalid JSON — send: {\"message\": \"hello\"}"}
            ))
            return

        message = data.get("message", "").strip()
        if not message:
            await self.send(text_data=json.dumps({"error": "Missing 'message' field"}))
            return

        if _is_question(message):
            # Step 2b: question — send only to the asking user (private group)
            # User B sees nothing until User A clicks "Share with team"
            await self.channel_layer.group_send(
                self.private_group,
                {
                    "type":       "chat.message",
                    "message":    message,
                    "sender":     self.user.username,
                    "is_private": True,   # UI renders it as a pending private message
                },
            )
            # Step 3: trigger RAG — AI reply will also arrive privately
            await self._publish_question(message)
        else:
            # Step 2a: regular message — broadcast to everyone in the room
            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type":    "chat.message",
                    "message": message,
                    "sender":  self.user.username,
                },
            )

    async def _publish_question(self, question: str):
        """
        Publish a chat.question event to the ai:events Redis Stream.

        FastAPI's AIStreamConsumer picks this up, runs vector search,
        and posts the answer back via /api/chat/bot-message/.

        WHY fire-and-forget (no await on response):
          The LLM/retrieval can take 1-5 seconds. We don't want to hold the
          WebSocket receive loop. The answer arrives asynchronously as a bot
          message broadcast — same path as any other message.
        """
        try:
            client = aioredis.from_url(REDIS_URL)
            await client.xadd(
                "ai:events",
                {
                    "event_type": "chat.question",
                    "payload": json.dumps({
                        "chat_id":  int(self.chat_id),   # URL route kwargs are strings
                        "org_id":   int(self.user.org_id),
                        "user_id":  int(self.user.id),
                        "username": self.user.username,
                        "question": question,
                    }),
                },
            )
            await client.aclose()
            logger.info(
                f"[WS] Published chat.question | chat={self.chat_id} | q={question[:60]}"
            )
        except Exception as e:
            logger.error(f"[WS] Failed to publish question to Redis: {e}")

    async def chat_message(self, event):
        """Receive broadcast from group, forward to this WebSocket client."""
        await self.send(text_data=json.dumps({
            "sender":     event["sender"],
            "message":    event["message"],
            "is_bot":     event.get("is_bot", False),
            "is_private": event.get("is_private", False),  # triggers action buttons
            "question":   event.get("question", ""),
        }))
