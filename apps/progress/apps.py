"""App configuration for the progress app."""

from __future__ import annotations

from django.apps import AppConfig


class ProgressConfig(AppConfig):
    """Learner progress: lesson completion, course completion, activity.

    Phase 6 extracted this domain from ``lessons`` — learner state is not
    lesson content, and the split keeps the dependency graph acyclic:
    ``progress → lessons → courses``, and neither content app knows learner
    state exists. Course completion is **derived** from lesson completion
    at read/write time, never counter-maintained. ``LearningActivity`` is
    the append-only foundation streaks, XP and leaderboards will read.
    See ``docs/adr/0012-progress-domain.md``.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.progress"
    label = "progress"
    verbose_name = "Learning progress"
