"""The editable legal documents."""

from __future__ import annotations

from django.db import models

from apps.core.models.base import TimeStampedModel
from apps.legal.constants import TITLE_MAX_LENGTH, LegalDocumentKind


class LegalDocument(TimeStampedModel):
    """One published legal document (terms, privacy, PDPA, cookie).

    Exactly one row per kind  the public page shows the current text and
    an administrator edits it in place. ``version`` increments on every
    content change, so "which version did the user see" is answerable by
    comparing ``User.terms_accepted_at`` with this row's ``updated_at``
    history in the audit sense, without keeping a revision table the
    product has no reader for yet.
    """

    kind = models.CharField(
        max_length=20, choices=LegalDocumentKind.choices, unique=True
    )
    title = models.CharField(max_length=TITLE_MAX_LENGTH)
    # Plain text with blank-line paragraphs; the frontend renders
    # paragraphs, not HTML  storing markup would make an admin textarea
    # an XSS vector into a public page.
    body = models.TextField()
    version = models.PositiveIntegerField(default=1)

    class Meta:
        verbose_name = "legal document"
        verbose_name_plural = "legal documents"
        ordering = ("kind",)

    def __str__(self) -> str:
        """Return the kind and version for the admin list."""
        return f"{self.kind} v{self.version}"
