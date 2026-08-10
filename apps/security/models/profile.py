"""The threat profile — the running summary for one source address."""

from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.security.constants import (
    NOTE_MAX_LENGTH,
    PATH_MAX_LENGTH,
    USER_AGENT_MAX_LENGTH,
    ReviewState,
    SignalKind,
    ThreatLevel,
)


class ThreatProfile(models.Model):
    """One row per source address: its current score, band and status.

    This is a **derived summary**, not a second source of truth. Every
    point in ``score`` came from a :class:`SecurityEvent`; the column
    exists because recomputing a decayed sum over every event on every
    dashboard render does not scale, and because filtering by band needs
    an index. The recount management command rebuilds it from the events
    whenever the two are suspected of disagreeing.

    ``level`` is likewise denormalised from ``score`` — always written
    together, never independently, so they cannot drift apart.

    An address, not a person: KawaiiBake never claims that one IP is one
    visitor. The dashboard says "แหล่งที่มา" for exactly this reason.
    """

    ip = models.GenericIPAddressField(unique=True)
    score = models.FloatField(default=0.0)
    level = models.CharField(
        max_length=10,
        choices=ThreatLevel.choices,
        default=ThreatLevel.LOW,
        db_index=True,
    )
    event_count = models.PositiveIntegerField(default=0)

    # Most-recent context, so the list view needs no join to be useful.
    last_kind = models.CharField(
        max_length=32, choices=SignalKind.choices, blank=True
    )
    last_path = models.CharField(max_length=PATH_MAX_LENGTH, blank=True)
    last_user_agent = models.CharField(
        max_length=USER_AGENT_MAX_LENGTH, blank=True
    )

    first_seen_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(db_index=True)

    # Enforcement. Null means "not blocked"; a past timestamp means the
    # block has lapsed. Never cleared to a boolean, so the history of
    # "was blocked until X" survives the block expiring.
    blocked_until = models.DateTimeField(null=True, blank=True)
    blocked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="security_blocks_issued",
    )

    # Operator triage.
    review_state = models.CharField(
        max_length=14,
        choices=ReviewState.choices,
        default=ReviewState.OPEN,
        db_index=True,
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="security_reviews",
    )
    note = models.CharField(max_length=NOTE_MAX_LENGTH, blank=True)

    class Meta:
        verbose_name = "threat profile"
        verbose_name_plural = "threat profiles"
        ordering = ("-score", "-last_seen_at")
        indexes = [
            models.Index(fields=["-score"], name="sec_profile_score_idx"),
            models.Index(
                fields=["level", "-last_seen_at"], name="sec_profile_level_idx"
            ),
        ]

    def __str__(self) -> str:
        """Return the address and its band."""
        return f"{self.ip} ({self.level})"
