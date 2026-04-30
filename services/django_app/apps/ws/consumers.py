"""
ChatConsumer — WebSocket consumer for real-time chat.

Authentication:
  JWT token must be passed as a query parameter on connect:
  ws://localhost:8000/ws/chat/1/?token=<access_token>

  - Token is validated BEFORE accept() — unauthenticated clients get close code 4001
  - User is attached to self.user for use in receive/broadcast
"""
import json
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import AccessToken

User = get_user_model()


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

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    # ── Messaging ─────────────────────────────────────────────────────────────

    async def receive(self, text_data):
        """Receive message from WebSocket client, broadcast to room group."""
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

        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "chat.message",
                "message": message,
                "sender": self.user.username,
            },
        )

    async def chat_message(self, event):
        """Receive broadcast from group, forward to this WebSocket client."""
        await self.send(text_data=json.dumps({
            "sender":   event["sender"],
            "message":  event["message"],
            "is_bot":   event.get("is_bot", False),
        }))
