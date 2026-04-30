"""
Document views — upload and list.

Design:
  POST /api/documents/upload/  — multipart upload, triggers AI pipeline via signal
  GET  /api/documents/?chat_id=<id> — list docs for a chat (org-scoped)

WHY we don't call FastAPI directly from here:
  The view saves the Document. The post_save signal publishes to Redis Stream.
  FastAPI consumes the stream. Decoupled — the view doesn't care what AI does.
  If FastAPI is down, the event sits in Redis Stream and replays when it recovers.
"""
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Document
from .serializers import DocumentResponseSerializer, DocumentUploadSerializer


class DocumentUploadView(APIView):
    """
    POST /api/documents/upload/
    Content-Type: multipart/form-data

    Body fields:
      file    — the document file (PDF or .txt)
      chat    — chat id the document belongs to
    """
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = DocumentUploadSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Inject org and uploaded_by — never trust the client for these
        # WHY: these are security-critical fields; client should never set them
        doc = serializer.save(
            org_id=request.user.org_id,   # from authenticated user — TenantMiddleware runs
            uploaded_by=request.user,     # before DRF JWT auth so request.org_id is not set
            status=Document.Status.PENDING,
        )

        # post_save signal fires here → publishes to Redis Stream (ai:events)
        # FastAPI stream consumer picks it up and starts ingestion

        return Response(
            DocumentResponseSerializer(doc).data,
            status=status.HTTP_201_CREATED,
        )


class DocumentListView(APIView):
    """
    GET /api/documents/?chat_id=<id>
    Returns all documents for a chat, scoped to the request's org.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        chat_id = request.query_params.get("chat_id")

        qs = Document.objects.for_org(request.user.org_id)
        if chat_id:
            qs = qs.filter(chat_id=chat_id)

        return Response(
            DocumentResponseSerializer(qs.order_by("-created_at"), many=True).data
        )
