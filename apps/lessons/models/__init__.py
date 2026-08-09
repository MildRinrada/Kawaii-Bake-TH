"""Lessons models — public API.

``LessonProgress`` moved to ``apps.progress`` in Phase 6 — learner progress
is its own domain (ADR 0012).
"""

from __future__ import annotations

from apps.lessons.models.lesson import Lesson

__all__ = ["Lesson"]
