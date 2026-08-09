"""Reconcile the published-lesson counters on courses.

The counters (count and total duration) are rebuildable caches pushed through
a single repository choke point; this command repairs them after any mutation
path that bypassed the API — most likely a change made in the Django admin.
"""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand
from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce

from apps.courses.services import course_service
from apps.lessons.constants import LessonStatus
from apps.lessons.models import Lesson


class Command(BaseCommand):
    """Recount every course's published lessons and push the results."""

    help = (
        "Rebuild Course.published_lesson_count and "
        "Course.published_duration_minutes from the lessons table."
    )

    def handle(self, *args: Any, **options: Any) -> None:
        """Recount and report how many courses changed."""
        published = Q(status=LessonStatus.PUBLISHED)
        stats = (
            Lesson.objects.values("course_id")
            .annotate(
                published=Count("id", filter=published),
                duration=Coalesce(
                    Sum("duration_minutes", filter=published), 0
                ),
            )
            .values_list("course_id", "published", "duration")
        )

        updated = 0
        for course_id, count, duration in stats:
            course_service.sync_published_lesson_count(
                course_id=course_id, count=count, duration_minutes=duration
            )
            updated += 1

        # Courses with zero lessons have no row above; reset them explicitly.
        from apps.courses.models import Course

        lesson_course_ids = Lesson.objects.values_list("course_id", flat=True)
        orphaned = Course.objects.exclude(pk__in=lesson_course_ids).filter(
            Q(published_lesson_count__gt=0) | Q(published_duration_minutes__gt=0)
        )
        for course in orphaned:
            course_service.sync_published_lesson_count(
                course_id=course.pk, count=0, duration_minutes=0
            )
            updated += 1

        self.stdout.write(self.style.SUCCESS(f"Recounted {updated} course(s)."))
