"""
User model — tenant-scoped with role-based access control (RBAC).

Roles:
  OWNER  — created when org is registered, full control
  ADMIN  — manage users within the org
  MEMBER — regular user, no admin rights

WHY AbstractUser: inherits username, password hashing, is_active,
                  last_login, date_joined — no need to rebuild auth primitives.
"""
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):

    class Role(models.TextChoices):
        OWNER  = "owner",  "Owner"
        ADMIN  = "admin",  "Admin"
        MEMBER = "member", "Member"

    org = models.ForeignKey(
        "orgs.Org",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="users",
    )
    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.MEMBER,
    )

    # Keep email unique — we use it as the login identifier
    email = models.EmailField(unique=True)

    class Meta:
        db_table = "users"

    def __str__(self):
        return f"{self.email} ({self.org_id})"

    @property
    def is_owner(self):
        return self.role == self.Role.OWNER

    @property
    def is_admin(self):
        return self.role in (self.Role.OWNER, self.Role.ADMIN)
