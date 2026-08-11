"""Business logic for legal-document editing."""

from __future__ import annotations

import logging

from apps.legal.exceptions import LegalDocumentNotFoundError
from apps.legal.models import LegalDocument
from apps.legal.repositories import legal_repository
from apps.legal.selectors import legal_selector

logger = logging.getLogger(__name__)


def update_document(
    *, kind: str, title: str | None, body: str | None, actor_id: int
) -> LegalDocument:
    """Edit a document's title and/or body, bumping its version.

    Args:
        kind: The document kind slug.
        title: Replacement title, or ``None`` to keep the current one.
        body: Replacement body, or ``None`` to keep the current one.
        actor_id: The staff user making the change, for the audit log.

    Returns:
        The updated document.

    Raises:
        LegalDocumentNotFoundError: If the kind does not exist.
    """
    document = legal_selector.get_document(kind=kind)
    if document is None:
        raise LegalDocumentNotFoundError

    document = legal_repository.update_document(
        document=document, title=title, body=body
    )
    # Legal text changes are exactly the kind of thing an audit asks
    # about later; one structured line answers who/what/when.
    logger.info(
        "legal_document_updated kind=%s version=%s by=%s",
        document.kind,
        document.version,
        actor_id,
    )
    return document
