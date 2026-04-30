"""
TenantMiddleware — injects org_id into every request.

Sits AFTER AuthenticationMiddleware so request.user is already resolved.

WHY: We want every view to have request.org_id available without
     manually querying the org on every endpoint. Middleware is the
     single enforcement point — no view can forget to scope by tenant.

Flow:
    Request → AuthMiddleware (resolves user) → TenantMiddleware (resolves org)
    → View has both request.user and request.org_id ready
"""

from django.http import JsonResponse


class TenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Unauthenticated requests (login, register) pass through
        if not request.user.is_authenticated:
            return self.get_response(request)

        # Authenticated requests must have an org
        org_id = getattr(request.user, "org_id", None)
        if org_id is None:
            return JsonResponse(
                {"error": "User is not associated with any organisation."},
                status=403,
            )

        request.org_id = org_id
        return self.get_response(request)
