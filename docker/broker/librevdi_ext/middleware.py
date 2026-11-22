"""Health endpoints that are answered before any upstream middleware (redirects, security checks).

* ``/healthz`` – liveness: the process answers
* ``/readyz``  – readiness: the default database answers
"""

import json

from django.db import connections
from django.http import HttpResponse


def _json(status: int, payload: dict) -> HttpResponse:
    return HttpResponse(json.dumps(payload), status=status, content_type="application/json")


class HealthMetricsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path
        if path == "/healthz":
            return _json(200, {"status": "ok"})
        if path == "/readyz":
            try:
                with connections["default"].cursor() as cursor:
                    cursor.execute("SELECT 1")
                    cursor.fetchone()
            except Exception as e:  # pylint: disable=broad-except
                return _json(503, {"status": "unavailable", "database": type(e).__name__})
            return _json(200, {"status": "ok", "database": "ok"})
        return self.get_response(request)
