"""App configuration for the recommendation app."""

from __future__ import annotations

from django.apps import AppConfig


class RecommendationConfig(AppConfig):
    """Recipe/course recommendations and ingredient substitution.

    A **pure consumer**: it reads facts other domains own — through their
    public selectors only — derives deterministic scores, and returns ranked
    results. It owns no tables (recommendations are derived, never stored),
    writes nothing back to any source domain, and no source domain knows it
    exists. Substitution is an explicit in-code rule registry keyed by the
    normalised ingredient name that ``recipes`` already stores — the future
    ingredient catalogue remains a declared seam, not a table.
    See ``docs/adr/0018-recommendation-and-substitution.md``.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.recommendation"
    verbose_name = "Recommendation"
