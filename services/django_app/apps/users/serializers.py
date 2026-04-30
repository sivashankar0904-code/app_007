"""
User serializers — control what data enters and leaves the API.

Three serializers, each with a specific job:
  RegisterSerializer  — create a new user (write-only for password)
  UserSerializer      — read a user's profile (no password ever)
  ChangePasswordSerializer — update password only
"""
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import User


class RegisterSerializer(serializers.ModelSerializer):
    """
    Used on POST /api/users/register/
    password field is write_only — it NEVER appears in any response.
    """
    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password],  # enforces Django's password rules
    )

    class Meta:
        model = User
        fields = ("id", "username", "email", "password", "role")
        extra_kwargs = {
            "role": {"required": False},  # defaults to MEMBER
        }

    def create(self, validated_data):
        # create_user hashes the password — never store plain text
        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            password=validated_data["password"],
            role=validated_data.get("role", User.Role.MEMBER),
            org=self.context.get("org"),  # injected from view
        )
        return user


class UserSerializer(serializers.ModelSerializer):
    """
    Used for GET responses — safe read-only view of a user.
    org_name is a computed field so clients don't need a second request.
    """
    org_name = serializers.CharField(source="org.name", read_only=True, default=None)

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "role",
            "org_id",
            "org_name",
            "is_active",
            "date_joined",
        )
        read_only_fields = fields  # all fields read-only on this serializer


class UpdateUserSerializer(serializers.ModelSerializer):
    """
    Used on PATCH /api/users/<id>/ — allow updating role and active status.
    Admins use this to promote/demote members.
    """
    class Meta:
        model = User
        fields = ("role", "is_active")


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(
        required=True,
        write_only=True,
        validators=[validate_password],
    )
