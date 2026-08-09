"""App configuration for the rewards app."""

from __future__ import annotations

from django.apps import AppConfig


class RewardsConfig(AppConfig):
    """The reward economy: account, immutable ledger, earn/spend/adjust.

    A pull-based consumer in the Phase 9 mould — source domains own the
    facts (progress, quizzes, certificates), rewards owns only the
    economic consequence, and no producer knows this app exists. Unlike
    the XP ledger's count arithmetic, every earning here is keyed to an
    **identified** source fact and made idempotent by a database unique
    constraint, because a currency must survive duplicate delivery under
    concurrency. See ``docs/adr/0019-rewards-economy.md``.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.rewards"
    verbose_name = "Rewards"
