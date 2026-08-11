"""The per-event-type opt-out row."""

from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.notifications.constants import NotificationEventType


class NotificationPreference(models.Model):
    """One user's explicit choice about one in-app event type.

    **Absent row means enabled**  rows exist only once a user changes a
    preference, so nothing is seeded per user and the default costs no
    storage. This table is a different axis from
    ``users.UserPreference``'s email toggles: users owns the *channel*
    (email on/off per broad category), this app owns the *event* (which
    happenings reach the in-app center). The two never overlap (ADR 0016).
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notification_preferences",
    )
    event_type = models.CharField(
        max_length=30, choices=NotificationEventType.choices
    )
    enabled = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "notification preference"
        verbose_name_plural = "notification preferences"
        constraints = [
            models.UniqueConstraint(
                fields=("user", "event_type"),
                name="notifications_one_pref_per_event",
            ),
        ]

    def __str__(self) -> str:
        """Return the preference description."""
        state = "on" if self.enabled else "off"
        return f"{self.event_type}={state} · user {self.user_id}"
