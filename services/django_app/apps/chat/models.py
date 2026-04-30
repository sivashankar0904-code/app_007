"""
Chat and Message models — tenant-scoped.
"""
from django.db import models
from core.managers.org_scoped import OrgScopedManager

class Chat(models.Model):
    org = models.ForeignKey("orgs.Org", on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    created_by = models.ForeignKey("users.User", on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = OrgScopedManager()

    class Meta:
        db_table = "chats"

class Message(models.Model):
    class SenderType(models.TextChoices):
        HUMAN = "human", "Human"
        BOT = "bot", "Bot"

    chat = models.ForeignKey(Chat, on_delete=models.CASCADE, related_name="messages")
    org = models.ForeignKey("orgs.Org", on_delete=models.CASCADE)
    sender = models.ForeignKey("users.User", on_delete=models.SET_NULL, null=True, blank=True)
    sender_type = models.CharField(max_length=10, choices=SenderType.choices, default=SenderType.HUMAN)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    objects = OrgScopedManager()

    class Meta:
        db_table = "messages"
        ordering = ["created_at"]
