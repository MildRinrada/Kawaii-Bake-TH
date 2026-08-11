"""Domain exceptions for the legal app."""

from __future__ import annotations

from apps.core.exceptions import DomainError


class LegalDocumentNotFoundError(DomainError):
    """Raised when a legal document kind cannot be located."""

    code = "legal_document_not_found"
    status_code = 404
    message = "Legal document not found."
