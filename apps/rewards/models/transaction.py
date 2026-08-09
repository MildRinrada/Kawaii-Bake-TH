"""The immutable reward ledger."""

from __future__ import annotations

from django.db import models
from django.db.models import Q

from apps.core.models.base import TimeStampedModel
from apps.rewards.constants import (
    EVENT_KEY_MAX_LENGTH,
    NOTE_MAX_LENGTH,
    RewardKind,
    RewardReason,
)


class RewardTransaction(TimeStampedModel):
    """One economic change, forever.

    Append-only in the ``XPTransaction``/``LearningActivity`` family: no
    service, repository or API updates or deletes a row — history is the
    audit trail. Each row answers the full "what/why/how much/balance
    afterward/which source event/when" set on its own.

    ``event_key`` is the idempotency anchor: the unique constraint on
    ``(account, event_key)`` is what makes duplicate delivery — retries,
    races, replays — structurally unable to grant twice. An `if exists`
    check would race; the constraint cannot.

    ``actor_handle`` is a Phase 10-style snapshot (public handle, no FK)
    populated only for staff adjustments, so the audit trail survives
    staff account changes.
    """

    account = models.ForeignKey(
        "rewards.RewardAccount",
        on_delete=models.CASCADE,
        related_name="transactions",
    )
    kind = models.CharField(max_length=20, choices=RewardKind.choices)
    amount = models.IntegerField(
        help_text="Signed: positive credits the balance, negative debits it."
    )
    balance_after = models.PositiveIntegerField()
    reason_code = models.CharField(max_length=40, choices=RewardReason.choices)
    event_key = models.CharField(max_length=EVENT_KEY_MAX_LENGTH)
    note = models.CharField(max_length=NOTE_MAX_LENGTH, blank=True)
    actor_handle = models.CharField(max_length=150, blank=True)

    class Meta:
        verbose_name = "reward transaction"
        verbose_name_plural = "reward transactions"
        ordering = ("-created_at", "-id")
        constraints = [
            models.UniqueConstraint(
                fields=("account", "event_key"), name="rewards_event_once"
            ),
            models.CheckConstraint(
                condition=~Q(amount=0), name="rewards_amount_nonzero"
            ),
        ]
        indexes = [
            models.Index(
                fields=["account", "-created_at"], name="rewards_history_idx"
            ),
        ]

    def __str__(self) -> str:
        """Return a readable label."""
        return f"{self.reason_code} · {self.amount:+d} · account {self.account_id}"
