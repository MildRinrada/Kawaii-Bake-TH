"""Quizzes models — public API."""

from __future__ import annotations

from apps.quizzes.models.attempt import QuizAttempt
from apps.quizzes.models.attempt_answer import QuizAttemptAnswer
from apps.quizzes.models.quiz import Quiz
from apps.quizzes.models.quiz_question import QuizQuestion

__all__ = ["Quiz", "QuizAttempt", "QuizAttemptAnswer", "QuizQuestion"]
