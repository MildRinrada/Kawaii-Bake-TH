"""The reward account  one materialized balance per user."""

from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.core.models.base import TimeStampedModel


class RewardAccount(TimeStampedModel):
    """One user's reward balance and lifetime totals.

    The balance is **materialized**  the one stored aggregate in this
    domain  because the summary endpoint and every spend guard would
    otherwise scan the ledger (Database.md's "counters need a proven read
    reason and a rebuild path" rule; this is the proven reason). The
    rebuild path is total: ``balance = Σ ledger amounts``,
    ``lifetime_earned = Σ positive``, ``lifetime_spent = Σ |negative|`` 
    `reconcile_rewards` recomputes all three from the ledger.

    All mutation goes through the repository's conditional-UPDATE
    (`F()`-expression) path inside the ledger transaction; nothing
    assigns these columns directly. ``PositiveIntegerField`` adds a
    database CHECK as the second net under the ``balance >= amount``
    spend guard, so a negative balance is structurally impossible.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="reward_account",
    )
    balance = models.PositiveIntegerField(default=0)
    lifetime_earned = models.PositiveIntegerField(default=0)
    lifetime_spent = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "reward account"
        verbose_name_plural = "reward accounts"

    def __str__(self) -> str:
        """Return a readable label."""
        return f"reward account · user {self.user_id} · {self.balance}"
