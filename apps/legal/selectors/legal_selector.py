"""Read-side access to legal documents."""

from __future__ import annotations

from apps.legal.models import LegalDocument


def list_documents() -> list[LegalDocument]:
    """Return every published document, ordered by kind.

    Returns:
        All legal documents.
    """
    return list(LegalDocument.objects.all())


def get_document(*, kind: str) -> LegalDocument | None:
    """Return one document by its kind slug.

    Args:
        kind: A :class:`~apps.legal.constants.LegalDocumentKind` value.

    Returns:
        The document, or ``None`` when the kind is unknown.
    """
    return LegalDocument.objects.filter(kind=kind).first()
