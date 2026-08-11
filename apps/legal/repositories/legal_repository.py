"""Write-side database access for legal documents."""

from __future__ import annotations

from django.db.models import F

from apps.legal.models import LegalDocument


def update_document(
    *, document: LegalDocument, title: str | None, body: str | None
) -> LegalDocument:
    """Apply an edit and bump the version in one atomic statement.

    The version bump uses an ``F`` expression so two concurrent editors
    cannot both read version 3 and both write version 4  the database
    increments whatever is current.

    Args:
        document: The document being edited.
        title: Replacement title, or ``None`` to keep the current one.
        body: Replacement body, or ``None`` to keep the current one.

    Returns:
        The updated document, re-read so ``version`` is concrete.
    """
    fields: dict[str, object] = {"version": F("version") + 1}
    if title is not None:
        fields["title"] = title
    if body is not None:
        fields["body"] = body
    LegalDocument.objects.filter(pk=document.pk).update(**fields)
    document.refresh_from_db()
    return document
