"""
Org model — the root tenant entity.
Every other model hangs off an Org via org_id (FK or direct field).
"""
from django.db import models

class Org(models.Model):
    name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "orgs"

    def __str__(self):
        return self.name
