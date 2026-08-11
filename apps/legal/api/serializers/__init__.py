"""Legal API serializers  public API."""

from __future__ import annotations

from apps.legal.api.serializers.legal_serializers import (
    LegalDocumentSerializer,
    LegalDocumentSummarySerializer,
    LegalDocumentUpdateSerializer,
)

__all__ = [
    "LegalDocumentSerializer",
    "LegalDocumentSummarySerializer",
    "LegalDocumentUpdateSerializer",
]
