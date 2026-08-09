"""Search infrastructure — public API."""

from __future__ import annotations

from django.conf import settings
from django.utils.module_loading import import_string

from infrastructure.search.base import SearchBackend
from infrastructure.search.simple_search import SimpleSearchBackend

DEFAULT_BACKEND = "infrastructure.search.simple_search.SimpleSearchBackend"


def get_search_backend() -> SearchBackend:
    """Return the configured search backend.

    Selected by ``settings.SEARCH_BACKEND``, following the same dotted-path
    pattern as ``AUTH_CREDENTIAL_ISSUER``.

    Returns:
        A :class:`SearchBackend` implementation.
    """
    path = getattr(settings, "SEARCH_BACKEND", DEFAULT_BACKEND)
    return import_string(path)()


__all__ = ["SearchBackend", "SimpleSearchBackend", "get_search_backend"]
