"""The security event — one observation, recorded once, never edited."""

from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.security.constants import (
    PATH_MAX_LENGTH,
    USER_AGENT_MAX_LENGTH,
    SignalKind,
    ThreatLevel,
)


class SecurityEvent(models.Model):
    """Something suspicious that happened, as observed at one moment.

    **Append-only.** There is no update path and no delete API: an event
    is evidence, and evidence that can be rewritten is worthless in an
    incident review. Operator triage happens on
    :class:`~apps.security.models.profile.ThreatProfile`, which is the
    mutable summary; the events underneath it stay frozen.

    ``actor`` is nullable and ``SET_NULL`` on purpose — most events come
    from anonymous traffic, and deleting a user account must not erase
    the record that their session did something. The row holds no email
    and no session key; ``ip`` and ``user_agent`` are the only
    identifying fields and both are already in the web server's logs.

    ``severity`` is stored rather than derived at read time so the admin
    list can filter and index on it, and so a later re-tuning of
    :data:`~apps.security.constants.SIGNAL_WEIGHTS` cannot silently
    rewrite history.
    """

    kind = models.CharField(max_length=32, choices=SignalKind.choices, db_index=True)
    severity = models.CharField(
        max_length=10, choices=ThreatLevel.choices, db_index=True
    )
    score_delta = models.FloatField(
        help_text="Points this observation added to the offender's score."
    )
    ip = models.GenericIPAddressField(db_index=True)
    user_agent = models.CharField(max_length=USER_AGENT_MAX_LENGTH, blank=True)
    path = models.CharField(max_length=PATH_MAX_LENGTH, blank=True)
    method = models.CharField(max_length=10, blank=True)
    status_code = models.PositiveSmallIntegerField(null=True, blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="security_events",
    )
    request_id = models.CharField(max_length=40, blank=True)
    detail = models.JSONField(
        default=dict,
        blank=True,
        help_text="Detector-specific context, e.g. the marker that matched.",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "security event"
        verbose_name_plural = "security events"
        ordering = ("-created_at", "-id")
        indexes = [
            # The offender drill-down: one address, newest first.
            models.Index(fields=["ip", "-created_at"], name="sec_event_ip_idx"),
            # The dashboard's default view and its kind/severity facets.
            models.Index(
                fields=["kind", "-created_at"], name="sec_event_kind_idx"
            ),
        ]

    def __str__(self) -> str:
        """Return a one-line description for admin listings."""
        return f"{self.kind} from {self.ip}"
