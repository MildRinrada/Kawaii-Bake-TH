"""App configuration for the Q&A app."""

from __future__ import annotations

from django.apps import AppConfig


class QaConfig(AppConfig):
    """Community questions and answers on recipes and courses.

    Deliberately **not** ``apps/questions``  that app is the quiz
    question bank (assessment items with answer keys); this one is open
    discussion between users. The two share nothing but the English word.
    Threads soft-delete (answers are other people's labor; deleting your
    question must not silently destroy their words); answers hard-delete
    (they are leaves). Notifications flow outward through the Phase 10
    push sink. See ``docs/adr/0017-community-gallery-and-qa.md``.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.qa"
    label = "qa"
    verbose_name = "Q&A"
