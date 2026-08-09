"""Request correlation middleware."""

from __future__ import annotations

import uuid
from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

REQUEST_ID_HEADER = "X-Request-ID"


class RequestIDMiddleware:
    """Attach a correlation id to every request and echo it back.

    The id is surfaced in API error envelopes, which makes a user-reported
    failure traceable to a single log line.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        """Store the next handler in the middleware chain."""
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """Assign ``request.request_id`` and mirror it onto the response."""
        incoming = request.headers.get(REQUEST_ID_HEADER)
        request.request_id = incoming or uuid.uuid4().hex  # type: ignore[attr-defined]
        response = self.get_response(request)
        response[REQUEST_ID_HEADER] = request.request_id  # type: ignore[attr-defined]
        return response
