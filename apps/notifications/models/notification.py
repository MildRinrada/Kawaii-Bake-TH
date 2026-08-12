"""The notification entity  a private snapshot of an event."""

from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.notifications.constants import (
    ACTOR_HANDLE_MAX_LENGTH,
    BODY_MAX_LENGTH,
    CTA_MAX_LENGTH,
    KIND_MAX_LENGTH,
    LINK_MAX_LENGTH,
    TITLE_MAX_LENGTH,
    AnnouncementKind,
    NotificationEventType,
)


class Notification(models.Model):
    """One event, as told to one recipient.

    **Snapshot, deliberately no FK to any content**  the reasoned
    departure from the ADR 0011 explicit-FK rule: reviews/favorites need
    FKs to compose visibility ``Q`` objects across joins, but a
    notification is private to its recipient and never joins anything.
    The only thing a content FK would add here is a CASCADE we do not
    want  deleting a recipe must not erase the recipient's history. The
    ``link`` is a frontend path that may go stale and 404 later; that is
    accepted (the assistant-context precedent, ADR 0013).

    ``actor_handle`` is the actor's public handle and nothing more  this
    row's content is rendered verbatim to the recipient, so no email or
    private field may ever enter it.

    The only mutations are the stamp-once ``read_at`` and ``clicked_at``
    (nullable timestamps, not booleans  the ``completed_at``
    convention). No ``updated_at``; there is nothing else to update. No
    delete API; history stays.
    """

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    event_type = models.CharField(
        max_length=30, choices=NotificationEventType.choices
    )
    title = models.CharField(max_length=TITLE_MAX_LENGTH)
    body = models.CharField(max_length=BODY_MAX_LENGTH, blank=True)
    actor_handle = models.CharField(
        max_length=ACTOR_HANDLE_MAX_LENGTH, blank=True
    )
    link = models.CharField(max_length=LINK_MAX_LENGTH, blank=True)
    # ADR 0030: staff campaigns carry their kind and call-to-action label
    # into the snapshot; machine events leave both blank and the frontend
    # draws them from `event_type`. `kind` is copied, not read through
    # the FK, for the same reason every other field here is: the row is
    # what the recipient was told, and editing a campaign must not
    # rewrite history. The campaign FK is aggregation-only (read and
    # click rates) - SET_NULL so deleting nothing erases a recipient's
    # history.
    kind = models.CharField(
        max_length=KIND_MAX_LENGTH,
        choices=AnnouncementKind.choices,
        blank=True,
    )
    cta_text = models.CharField(max_length=CTA_MAX_LENGTH, blank=True)
    campaign = models.ForeignKey(
        "notifications.NotificationCampaign",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deliveries",
    )
    read_at = models.DateTimeField(null=True, blank=True)
    # Stamp-once, like `read_at`: the recipient followed this row's link.
    # Reported by the client, so it is a *lower bound* on real clicks -
    # see `record_click` and the analytics panel, which says so.
    clicked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "notification"
        verbose_name_plural = "notifications"
        ordering = ("-created_at", "-id")
        indexes = [
            # The list page: recipient's feed, newest first.
            models.Index(
                fields=["recipient", "-created_at"], name="notif_recipient_idx"
            ),
            # The unread count / unread filter.
            models.Index(
                fields=["recipient", "read_at"], name="notif_unread_idx"
            ),
        ]

    def __str__(self) -> str:
        """Return the notification description."""
        return f"{self.event_type} → user {self.recipient_id}"
