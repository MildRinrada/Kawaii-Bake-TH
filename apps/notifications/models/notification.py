"""The notification entity — a private snapshot of an event."""

from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.notifications.constants import (
    ACTOR_HANDLE_MAX_LENGTH,
    BODY_MAX_LENGTH,
    LINK_MAX_LENGTH,
    TITLE_MAX_LENGTH,
    NotificationEventType,
)


class Notification(models.Model):
    """One event, as told to one recipient.

    **Snapshot, deliberately no FK to any content** — the reasoned
    departure from the ADR 0011 explicit-FK rule: reviews/favorites need
    FKs to compose visibility ``Q`` objects across joins, but a
    notification is private to its recipient and never joins anything.
    The only thing a content FK would add here is a CASCADE we do not
    want — deleting a recipe must not erase the recipient's history. The
    ``link`` is a frontend path that may go stale and 404 later; that is
    accepted (the assistant-context precedent, ADR 0013).

    ``actor_handle`` is the actor's public handle and nothing more — this
    row's content is rendered verbatim to the recipient, so no email or
    private field may ever enter it.

    The one mutation is the stamp-once ``read_at`` (nullable timestamp,
    not a boolean — the ``completed_at`` convention). No ``updated_at``;
    there is nothing else to update. No delete API; history stays.
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
    read_at = models.DateTimeField(null=True, blank=True)
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
