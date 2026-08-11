"""Per-course certificate template designs (ADR 0029).

The design document is a JSON scene graph the admin designer edits:
absolutely-positioned elements (dynamic fields, static text, images,
signatures, boxes) over a fixed-size canvas. Draft and published live
side by side on the same row — saving the editor state and changing the
production template are different acts, so an operator can experiment
freely and publish deliberately.

The document is data, never markup: the frontend renders it through
React with typed style properties, so nothing in here can become HTML.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.core.models.base import TimeStampedModel


class CertificateTemplate(TimeStampedModel):
    """One course's certificate design.

    ``draft_design`` is the editor's working copy (autosaved);
    ``published_design`` is what "Publish" last froze. A course without a
    row simply uses the built-in default design.
    """

    course = models.OneToOneField(
        "courses.Course",
        on_delete=models.CASCADE,
        related_name="certificate_template",
    )
    draft_design = models.JSONField()
    published_design = models.JSONField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="certificate_templates_edited",
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "certificate template"
        verbose_name_plural = "certificate templates"
        ordering = ("-updated_at", "-id")

    def __str__(self) -> str:
        """Return the owning course id (title lives on the course)."""
        return f"template for course {self.course_id}"
