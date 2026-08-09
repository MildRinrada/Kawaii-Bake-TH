"""Q&A models — public API."""

from __future__ import annotations

from apps.qa.models.answer import QuestionAnswer
from apps.qa.models.thread import QuestionThread

__all__ = ["QuestionAnswer", "QuestionThread"]
