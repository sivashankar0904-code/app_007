"""
OrgScopedManager — base queryset manager for every multi-tenant model.

Every model that has an `org_id` field inherits this.
Calling .for_org(org_id) filters all queries to that tenant automatically.

WHY: Shared-schema multi-tenancy requires a hard boundary at the ORM layer.
     If a query ever runs without for_org(), it sees ALL tenants' data — a
     data leak. This manager makes the safe path the easy path.
"""

from django.db import models


class OrgScopedQuerySet(models.QuerySet):
    def for_org(self, org_id):
        return self.filter(org_id=org_id)


class OrgScopedManager(models.Manager):
    def get_queryset(self):
        return OrgScopedQuerySet(self.model, using=self._db)

    def for_org(self, org_id):
        return self.get_queryset().for_org(org_id)
