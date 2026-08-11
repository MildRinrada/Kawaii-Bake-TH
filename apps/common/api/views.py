"""Shared API view bases.

Views stay thin: parse the request into primitives, call a service or selector,
serialise the result. They never contain business logic and never query the ORM.
"""

from __future__ import annotations

from django.db.models import QuerySet
from django.http import HttpRequest
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.views.decorators.csrf import csrf_protect
from rest_framework.pagination import BasePagination
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer
from rest_framework.views import APIView

from apps.common.api.pagination import DefaultPageNumberPagination


def client_ip(request: HttpRequest) -> str:
    """Extract the originating client IP address.

    Trusts ``X-Forwarded-For`` only for its first entry, which is what a
    correctly configured reverse proxy appends.

    Args:
        request: The incoming request.

    Returns:
        The client IP, or an empty string when it cannot be determined.
    """
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "") or ""


class ServiceAPIView(APIView):
    """Base view for endpoints that delegate to the service layer."""

    def get_serializer_context(self) -> dict[str, object]:
        """Return the context passed to serializers.

        Includes ``request`` so serializers can build absolute media URLs  the
        frontend runs on a different origin and cannot resolve relative paths.
        """
        return {"request": self.request}


class PaginatedServiceAPIView(ServiceAPIView):
    """Base view for endpoints returning a paginated collection.

    Deliberately **not** ``GenericAPIView``: that class ships ``queryset`` and
    ``get_object()``, the two attributes the architecture bans because they run
    ORM in the HTTP layer. Inheriting them and promising not to use them is the
    slow dissolution the guidelines warn about.

    This base exposes only what is needed to paginate a **selector's** queryset.
    The selector returns a lazy queryset; the ORM executes here, at the edge,
    once the paginator has applied its slice.
    """

    pagination_class = DefaultPageNumberPagination

    @cached_property
    def paginator(self) -> BasePagination:
        """Return the paginator instance for this request."""
        return self.pagination_class()

    def paginated_response(
        self, queryset: QuerySet, serializer_class: type[BaseSerializer]
    ) -> Response:
        """Serialise one page of ``queryset``.

        Args:
            queryset: A lazy queryset produced by a selector.
            serializer_class: Serializer applied to the page, with ``many=True``.

        Returns:
            A ``{count, next, previous, results}`` response.
        """
        page = self.paginator.paginate_queryset(queryset, self.request, view=self)
        data = serializer_class(
            page, many=True, context=self.get_serializer_context()
        ).data
        return self.paginator.get_paginated_response(data)


@method_decorator(csrf_protect, name="dispatch")
class CsrfProtectedAPIView(ServiceAPIView):
    """Base view for **unauthenticated** state-changing endpoints.

    DRF wraps every ``APIView`` in ``csrf_exempt`` and only enforces CSRF from
    within ``SessionAuthentication``  which runs solely for already
    authenticated requests. Without this decorator, ``/login/`` and
    ``/register/`` would be CSRF-exempt, enabling login-CSRF (forcing a victim
    into an attacker-controlled account).
    """
