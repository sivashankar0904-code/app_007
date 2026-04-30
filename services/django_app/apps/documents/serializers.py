"""
Document serializers.

WHY a separate serializer for upload vs response:
  Upload accepts a file + chat_id (input).
  Response returns doc metadata (output).
  Splitting them keeps each serializer focused — single responsibility.
"""
from rest_framework import serializers
from .models import Document


class DocumentUploadSerializer(serializers.ModelSerializer):
    """Validates inbound multipart upload request."""

    class Meta:
        model = Document
        fields = ["chat", "file"]

    def validate_file(self, value):
        """
        Reject files that are too large or wrong type.
        WHY here and not in the view: validation belongs in the serializer —
        keeps the view thin and makes this testable in isolation.
        """
        max_size_mb = 10
        allowed_types = ["application/pdf", "text/plain"]

        if value.size > max_size_mb * 1024 * 1024:
            raise serializers.ValidationError(
                f"File too large. Max size is {max_size_mb}MB."
            )
        if value.content_type not in allowed_types:
            raise serializers.ValidationError(
                f"Unsupported file type '{value.content_type}'. "
                "Allowed: PDF, plain text."
            )
        return value


class DocumentResponseSerializer(serializers.ModelSerializer):
    """Shapes the API response after a successful upload."""

    uploaded_by = serializers.StringRelatedField()

    class Meta:
        model = Document
        fields = ["id", "file", "status", "uploaded_by", "created_at"]
        read_only_fields = fields
