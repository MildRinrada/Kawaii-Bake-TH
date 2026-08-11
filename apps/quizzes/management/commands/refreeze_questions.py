"""Restore missing freeze states from attempt history.

Lives in **quizzes** because only this domain knows which questions have been
attempted  the questions app owns the ``frozen_at`` state but cannot rebuild
it without inverting the dependency. Communication is the public service API,
never another app's models.

Strictly monotonic: it adds freezes that are missing and never removes one.
An abandoned attempt may leave a question frozen with no surviving answers;
over-freezing is the safe direction and stays untouched.
"""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand

from apps.questions.services import question_service
from apps.quizzes.models import QuizAttemptAnswer


class Command(BaseCommand):
    """Re-push ``frozen_at`` for every question with attempt history."""

    help = (
        "Freeze every question referenced by attempt history that is not "
        "already frozen. Repairs drift (e.g. admin edits); never unfreezes."
    )

    def handle(self, *args: Any, **options: Any) -> None:
        """Collect attempted question ids and push them through the public API."""
        question_ids = list(
            QuizAttemptAnswer.objects.values_list("question_id", flat=True).distinct()
        )
        question_service.freeze_questions(question_ids=question_ids)
        self.stdout.write(
            self.style.SUCCESS(
                f"Checked {len(question_ids)} attempted question(s); "
                "missing freeze states restored."
            )
        )
