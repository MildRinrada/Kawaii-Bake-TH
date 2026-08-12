"""Staff campaigns and reusable composer templates (ADR 0030)."""

from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.notifications.constants import (
    BODY_MAX_LENGTH,
    CTA_MAX_LENGTH,
    KIND_MAX_LENGTH,
    LINK_MAX_LENGTH,
    TEMPLATE_NAME_MAX_LENGTH,
    TITLE_MAX_LENGTH,
    AnnouncementKind,
    CampaignStatus,
)


def default_audience() -> dict:
    """The audience a fresh campaign starts with: everyone active."""
    return {"kind": "all"}


class NotificationCampaign(models.Model):
    """One staff-authored send: content, audience, and its lifecycle.

    The campaign is the admin-side record; delivery still produces the
    same per-recipient :class:`Notification` snapshots every machine
    event produces (rows carry a nullable ``campaign`` backreference so
    read receipts can be aggregated). ``title``/``body`` may embed
    ``{{variables}}``; they are resolved per recipient at send time and
    the *resolved* text is what lands in each snapshot.

    ``sent`` rows are immutable evidence: ``sent_at`` and
    ``recipients_count`` are stamped once and no update endpoint touches
    a sent campaign - duplicating is how staff iterate on one.
    """

    # The kind is presentation *and* meaning: one glyph and one colour
    # per value, chosen by the design system rather than typed by the
    # sender (which is what the retired `icon` emoji field was).
    kind = models.CharField(
        max_length=KIND_MAX_LENGTH,
        choices=AnnouncementKind.choices,
        default=AnnouncementKind.GENERAL,
    )
    title = models.CharField(max_length=TITLE_MAX_LENGTH)
    body = models.CharField(max_length=BODY_MAX_LENGTH, blank=True)
    cta_text = models.CharField(max_length=CTA_MAX_LENGTH, blank=True)
    link = models.CharField(max_length=LINK_MAX_LENGTH, blank=True)
    audience = models.JSONField(default=default_audience)
    status = models.CharField(
        max_length=12,
        choices=CampaignStatus.choices,
        default=CampaignStatus.DRAFT,
    )
    scheduled_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    recipients_count = models.PositiveIntegerField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notification_campaigns",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "notification campaign"
        verbose_name_plural = "notification campaigns"
        ordering = ("-created_at", "-id")
        indexes = [
            # The tabbed list: one status, newest first.
            models.Index(
                fields=["status", "-created_at"], name="campaign_status_idx"
            ),
            # The dispatcher's due-scan.
            models.Index(
                fields=["status", "scheduled_at"], name="campaign_due_idx"
            ),
        ]

    def __str__(self) -> str:
        """Return the campaign description."""
        return f"campaign {self.pk} [{self.status}] {self.title[:40]}"


class NotificationTemplate(models.Model):
    """A reusable starting point for the composer.

    Admin-side configuration only - templates never reach a recipient
    themselves and have nothing to do with per-user notification
    preferences. Archiving hides a template from the picker without
    breaking campaigns that were started from it (campaigns copy, never
    reference).
    """

    name = models.CharField(max_length=TEMPLATE_NAME_MAX_LENGTH)
    kind = models.CharField(
        max_length=KIND_MAX_LENGTH,
        choices=AnnouncementKind.choices,
        default=AnnouncementKind.GENERAL,
    )
    title = models.CharField(max_length=TITLE_MAX_LENGTH)
    body = models.CharField(max_length=BODY_MAX_LENGTH, blank=True)
    cta_text = models.CharField(max_length=CTA_MAX_LENGTH, blank=True)
    link = models.CharField(max_length=LINK_MAX_LENGTH, blank=True)
    is_archived = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notification_templates",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "notification template"
        verbose_name_plural = "notification templates"
        ordering = ("is_archived", "name", "id")

    def __str__(self) -> str:
        """Return the template description."""
        return f"template {self.pk} {self.name}"
