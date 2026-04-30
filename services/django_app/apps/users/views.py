"""
User views — IAM endpoints.

Endpoints:
  POST   /api/users/register/       → create user (admin/owner only)
  GET    /api/users/                → list users in your org
  GET    /api/users/me/             → your own profile
  GET    /api/users/<id>/           → single user detail
  PATCH  /api/users/<id>/           → update role or active status
  POST   /api/users/<id>/change-password/ → change own password

WHY ViewSets: DRF ViewSets combine list + detail into one class,
              reduce boilerplate, play nicely with routers.
"""
from django.contrib.auth import authenticate
from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from core.permissions.org_permission import IsOrgAdmin
from .models import User
from .serializers import (
    ChangePasswordSerializer,
    RegisterSerializer,
    UpdateUserSerializer,
    UserSerializer,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _tokens_for(user):
    """Return JWT access + refresh tokens for a user."""
    refresh = RefreshToken.for_user(user)
    return {
        "refresh": str(refresh),
        "access":  str(refresh.access_token),
    }


# ── Auth views ─────────────────────────────────────────────────────────────────

class LoginView(APIView):
    """
    POST /api/users/login/
    Body: { "email": "...", "password": "..." }
    Returns JWT tokens on success.
    Public endpoint — no auth required.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email    = request.data.get("email", "").strip().lower()
        password = request.data.get("password", "")

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"error": "Invalid credentials."}, status=status.HTTP_401_UNAUTHORIZED)

        # authenticate checks the hashed password
        user = authenticate(request, username=user.username, password=password)
        if not user:
            return Response({"error": "Invalid credentials."}, status=status.HTTP_401_UNAUTHORIZED)

        if not user.is_active:
            return Response({"error": "Account is deactivated."}, status=status.HTTP_403_FORBIDDEN)

        return Response({
            "user":   UserSerializer(user).data,
            "tokens": _tokens_for(user),
        })


class RegisterView(generics.CreateAPIView):
    """
    POST /api/users/register/
    Admin/Owner can create users inside their org.
    The org is automatically injected from request — users can't pick their org.
    """
    serializer_class = RegisterSerializer
    permission_classes = [permissions.IsAuthenticated, IsOrgAdmin]

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        # Inject the requesting user's org — tenant boundary enforced here
        ctx["org"] = self.request.user.org
        return ctx

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            {"user": UserSerializer(user).data, "tokens": _tokens_for(user)},
            status=status.HTTP_201_CREATED,
        )


# ── Profile views ──────────────────────────────────────────────────────────────

class MeView(generics.RetrieveAPIView):
    """GET /api/users/me/ — authenticated user's own profile."""
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class UserListView(generics.ListAPIView):
    """
    GET /api/users/
    Returns all users in the requesting user's org.
    OrgScopedManager + for_org() enforces tenant boundary at queryset level.
    """
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated, IsOrgAdmin]

    def get_queryset(self):
        return User.objects.filter(org=self.request.user.org).order_by("date_joined")


class UserDetailView(generics.RetrieveUpdateAPIView):
    """
    GET  /api/users/<id>/  — fetch user detail
    PATCH /api/users/<id>/ — update role or active status (admin only)
    """
    permission_classes = [permissions.IsAuthenticated, IsOrgAdmin]

    def get_serializer_class(self):
        if self.request.method in ("PATCH", "PUT"):
            return UpdateUserSerializer
        return UserSerializer

    def get_queryset(self):
        # Can only access users in own org — never cross-tenant
        return User.objects.filter(org=self.request.user.org)


class ChangePasswordView(APIView):
    """POST /api/users/<id>/change-password/ — change own password."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        # Users can only change their own password
        if request.user.pk != int(pk):
            return Response({"error": "Forbidden."}, status=status.HTTP_403_FORBIDDEN)

        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if not request.user.check_password(serializer.validated_data["old_password"]):
            return Response({"error": "Old password is incorrect."}, status=status.HTTP_400_BAD_REQUEST)

        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save()
        return Response({"message": "Password updated."})
