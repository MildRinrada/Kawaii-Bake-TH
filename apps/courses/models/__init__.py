"""Courses models — public API."""

from __future__ import annotations

from apps.courses.models.course import Course, thumbnail_upload_to
from apps.courses.models.enrollment import Enrollment

__all__ = ["Course", "Enrollment", "thumbnail_upload_to"]
