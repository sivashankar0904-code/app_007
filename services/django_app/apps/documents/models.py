"""
Document model — upload triggers AI processing pipeline via signals.
"""
from django.db import models
from core.managers.org_scoped import OrgScopedManager

class Document(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        READY = "ready", "Ready"
        FAILED = "failed", "Failed"

    org = models.ForeignKey("orgs.Org", on_delete=models.CASCADE)
    chat = models.ForeignKey("chat.Chat", on_delete=models.CASCADE, related_name="documents")
    uploaded_by = models.ForeignKey("users.User", on_delete=models.SET_NULL, null=True)
    file = models.FileField(upload_to="documents/%Y/%m/")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = OrgScopedManager()

    class Meta:
        db_table = "documents"
