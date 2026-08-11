"""Reconcile the rating aggregates stored on courses.

The aggregate pair (average, count) is a rebuildable cache pushed through the
review repository choke point (ADR 0021); this command repairs it after any
mutation path that bypassed the API  most likely a change made in the
Django admin.
"""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand

from apps.reviews.models import Review
from apps.reviews.repositories import review_repository


class Command(BaseCommand):
    """Recompute every reviewed course's rating aggregate and push it."""

    help = "Rebuild Course.rating_average / rating_count from the reviews table."

    def handle(self, *args: Any, **options: Any) -> None:
        """Resync each course that has (or ever had) course reviews."""
        course_ids = set(
            Review.objects.exclude(course_id=None).values_list(
                "course_id", flat=True
            )
        )
        for course_id in sorted(course_ids):
            review_repository.sync_course_rating(course_id=course_id)

        # Courses whose reviews were all hard-deleted keep stale aggregates;
        # reset any course carrying a count with no backing rows.
        from apps.courses.models import Course

        stale = Course.objects.filter(rating_count__gt=0).exclude(
            pk__in=course_ids
        )
        for course in stale:
            review_repository.sync_course_rating(course_id=course.pk)

        self.stdout.write(
            self.style.SUCCESS(
                f"Rebuilt rating aggregates for {len(course_ids)} course(s)."
            )
        )
