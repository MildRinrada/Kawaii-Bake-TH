"""Serializers for the staff progress surface."""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.common.api.serializers import PaginatedFilterSerializer
from apps.courses.constants import EnrollmentStatus


class ProgressSummarySerializer(serializers.Serializer):
    """Headline platform-learning totals."""

    enrollments_total = serializers.IntegerField(read_only=True)
    enrollments_active = serializers.IntegerField(read_only=True)
    enrollments_completed = serializers.IntegerField(read_only=True)
    enrollments_dropped = serializers.IntegerField(read_only=True)
    learners = serializers.IntegerField(read_only=True)
    lessons_completed = serializers.IntegerField(read_only=True)
    active_learners_7d = serializers.IntegerField(read_only=True)


class CourseStatRowSerializer(serializers.Serializer):
    """One course's enrollment funnel."""

    id = serializers.IntegerField(read_only=True)
    slug = serializers.CharField(read_only=True)
    title = serializers.CharField(read_only=True)
    status = serializers.CharField(read_only=True)
    published_lesson_count = serializers.IntegerField(read_only=True)
    enrolled_count = serializers.IntegerField(read_only=True)
    active_count = serializers.IntegerField(read_only=True)
    completed_count = serializers.IntegerField(read_only=True)
    dropped_count = serializers.IntegerField(read_only=True)
    completion_rate = serializers.SerializerMethodField()

    def get_completion_rate(self, obj: Any) -> int:
        """Completed enrollments as a percentage of all enrollments."""
        if not obj.enrolled_count:
            return 0
        return round(obj.completed_count * 100 / obj.enrolled_count)


class CourseStatFilterSerializer(PaginatedFilterSerializer):
    """Query parameters accepted by the per-course stats list."""

    search = serializers.CharField(
        max_length=120, required=False, allow_blank=True
    )


class LearnerRowSerializer(serializers.Serializer):
    """One learner on a course roster.

    Built from a dict the view assembles (enrollment + batch progress
    lookups), not from a model row.
    """

    username = serializers.CharField(read_only=True)
    display_name = serializers.CharField(read_only=True)
    avatar_url = serializers.CharField(read_only=True, allow_null=True)
    status = serializers.CharField(read_only=True)
    enrolled_at = serializers.DateTimeField(read_only=True)
    completed_at = serializers.DateTimeField(read_only=True, allow_null=True)
    completed_lessons = serializers.IntegerField(read_only=True)
    total_lessons = serializers.IntegerField(read_only=True)
    percent = serializers.IntegerField(read_only=True)
    last_activity_at = serializers.DateTimeField(read_only=True, allow_null=True)


class LearnerFilterSerializer(PaginatedFilterSerializer):
    """Query parameters accepted by the course roster."""

    status = serializers.ChoiceField(
        choices=EnrollmentStatus.choices, required=False, allow_blank=True
    )
    search = serializers.CharField(
        max_length=120, required=False, allow_blank=True
    )
