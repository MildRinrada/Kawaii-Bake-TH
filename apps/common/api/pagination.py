"""Pagination for list endpoints."""

from __future__ import annotations

from rest_framework.pagination import PageNumberPagination


class DefaultPageNumberPagination(PageNumberPagination):
    """Page-number pagination with a client-adjustable, capped page size.

    Returns DRF's standard ``{count, next, previous, results}`` envelope. That
    shape is deliberate: swapping to ``CursorPagination`` later, when
    ``COUNT(*)`` per request becomes the bottleneck, preserves it exactly.
    """

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100
