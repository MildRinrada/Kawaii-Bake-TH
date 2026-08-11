"""App configuration for the gamification app."""

from __future__ import annotations

from django.apps import AppConfig


class GamificationConfig(AppConfig):
    """XP ledger, levels, daily streaks and the leaderboard.

    A **pure consumer**: every point of XP is derived from facts other
    domains own (progress activity, certificates, quiz attempts, reviews),
    read through their public selectors  nothing is ever pushed in, no
    model signals exist, and no domain imports this app. Rewards, coupons,
    missions and seasonal events are future phases.
    See ``docs/adr/0015-gamification-foundation.md``.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.gamification"
    label = "gamification"
    verbose_name = "Gamification"
