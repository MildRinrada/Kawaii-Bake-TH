"""Legal API views  public API."""

from __future__ import annotations

from apps.legal.api.views.legal_views import (
    LegalDocumentDetailView,
    LegalDocumentListView,
)

__all__ = ["LegalDocumentDetailView", "LegalDocumentListView"]
