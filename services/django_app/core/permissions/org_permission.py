"""
Org-scoped DRF permission classes.

IsOrgAdmin — only owners and admins pass.
             Used on endpoints that modify users (create, update, deactivate).
"""
from rest_framework.permissions import BasePermission


class IsOrgAdmin(BasePermission):
    """Allow access only to users with role OWNER or ADMIN."""
    message = "You must be an org admin to perform this action."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.is_admin  # property on User model
        )
