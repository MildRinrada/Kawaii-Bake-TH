"""Single translation point from exceptions to the JSON error envelope.

Wired via ``REST_FRAMEWORK["EXCEPTION_HANDLER"]``. Because every domain error
carries its own code and status, views contain no ``try``/``except``.

Envelope shape::

    {"error": {"code": "...", "message": "...", "details": {...}, "request_id": "..."}}
"""

from __future__ import annotations

import logging
from typing import Any

from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from rest_framework import status as http_status
from rest_framework.exceptions import (
    APIException,
    AuthenticationFailed,
    NotAuthenticated,
    PermissionDenied,
    Throttled,
)
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from apps.core.exceptions import DomainError

logger = logging.getLogger("kawaiibake.api")


def _envelope(
    *,
    code: str,
    message: str,
    status_code: int,
    request_id: str,
    details: Any = None,
) -> Response:
    """Build the standard error response.

    Args:
        code: Stable machine-readable error identifier.
        message: Display-ready description.
        status_code: HTTP status to return.
        request_id: Correlation id from ``RequestIDMiddleware``.
        details: Optional field-level errors.

    Returns:
        The rendered error :class:`Response`.
    """
    return Response(
        {
            "error": {
                "code": code,
                "message": message,
                "details": details or {},
                "request_id": request_id,
            }
        },
        status=status_code,
    )


def _normalise_details(detail: Any) -> dict[str, Any]:
    """Coerce a DRF validation detail into a ``{field: [messages]}`` mapping."""
    if isinstance(detail, dict):
        return {key: value if isinstance(value, list) else [value] for key, value in detail.items()}
    if isinstance(detail, list):
        return {"non_field_errors": detail}
    return {"non_field_errors": [str(detail)]}


def api_exception_handler(exc: Exception, context: dict[str, Any]) -> Response:
    """Translate any exception raised in the API layer into the envelope.

    Args:
        exc: The exception raised while handling the request.
        context: DRF handler context containing ``request`` and ``view``.

    Returns:
        A :class:`Response` carrying the error envelope.
    """
    request = context.get("request")
    request_id: str = getattr(request, "request_id", "") if request is not None else ""

    # 1. Domain errors — the common case. DRF's default handler returns None for
    #    these, which would surface as an unhandled 500.
    if isinstance(exc, DomainError):
        return _envelope(
            code=exc.code,
            message=exc.message,
            status_code=exc.status_code,
            request_id=request_id,
            details=exc.details,
        )

    # 2. DRF serializer validation.
    if isinstance(exc, DRFValidationError):
        return _envelope(
            code="validation_error",
            message="The submitted data is invalid.",
            status_code=http_status.HTTP_400_BAD_REQUEST,
            request_id=request_id,
            details=_normalise_details(exc.detail),
        )

    # 3. Authentication. SessionAuthentication returns no WWW-Authenticate
    #    header, so DRF would answer 403; Next.js clients branch on 401.
    if isinstance(exc, NotAuthenticated | AuthenticationFailed):
        return _envelope(
            code="not_authenticated",
            message="Authentication credentials were not provided or are invalid.",
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            request_id=request_id,
        )

    if isinstance(exc, PermissionDenied):
        return _envelope(
            code="permission_denied",
            message="You do not have permission to perform this action.",
            status_code=http_status.HTTP_403_FORBIDDEN,
            request_id=request_id,
        )

    if isinstance(exc, Http404):
        return _envelope(
            code="not_found",
            message="The requested resource was not found.",
            status_code=http_status.HTTP_404_NOT_FOUND,
            request_id=request_id,
        )

    if isinstance(exc, Throttled):
        response = _envelope(
            code="rate_limited",
            message="Too many requests. Please try again later.",
            status_code=http_status.HTTP_429_TOO_MANY_REQUESTS,
            request_id=request_id,
        )
        if exc.wait is not None:
            response["Retry-After"] = str(int(exc.wait))
        return response

    # 4. Domain validators raise Django's ValidationError; DRF only converts it
    #    automatically inside `Field.run_validators`.
    if isinstance(exc, DjangoValidationError):
        details = (
            exc.message_dict
            if hasattr(exc, "message_dict")
            else {"non_field_errors": list(exc.messages)}
        )
        return _envelope(
            code="validation_error",
            message="The submitted data is invalid.",
            status_code=http_status.HTTP_400_BAD_REQUEST,
            request_id=request_id,
            details=details,
        )

    # 5. Any other DRF exception keeps its status but gains the envelope.
    drf_response = drf_exception_handler(exc, context)
    if drf_response is not None:
        detail = getattr(exc, "detail", None)
        message = str(detail) if detail is not None else "Request failed."
        code = getattr(exc, "default_code", "error") if isinstance(exc, APIException) else "error"
        return _envelope(
            code=code,
            message=message,
            status_code=drf_response.status_code,
            request_id=request_id,
        )

    # 6. Unexpected: log the traceback, never leak it to the client.
    logger.exception("Unhandled exception in API layer", extra={"request_id": request_id})
    return _envelope(
        code="internal_error",
        message="An unexpected error occurred.",
        status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
        request_id=request_id,
    )
