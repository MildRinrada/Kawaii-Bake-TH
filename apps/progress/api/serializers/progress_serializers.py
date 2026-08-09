"""Serializers for learner progress payloads."""

from __future__ import annotations

from rest_framework import serializers


class LessonCompletionSerializer(serializers.Serializer):
    """Response of completing a lesson."""

    lesson_id = serializers.IntegerField(read_only=True)
    completed = serializers.BooleanField(read_only=True)
    completed_at = serializers.DateTimeField(read_only=True, allow_null=True)
    first_completed_at = serializers.DateTimeField(read_only=True, allow_null=True)
    course_completed = serializers.BooleanField(read_only=True)


class LessonProgressItemSerializer(serializers.Serializer):
    """One row of the course progress report."""

    id = serializers.IntegerField(read_only=True)
    title = serializers.CharField(read_only=True)
    position = serializers.IntegerField(read_only=True)
    duration_minutes = serializers.IntegerField(read_only=True)
    is_preview = serializers.BooleanField(read_only=True)
    completed = serializers.BooleanField(read_only=True)
    completed_at = serializers.DateTimeField(read_only=True, allow_null=True)
    first_completed_at = serializers.DateTimeField(read_only=True, allow_null=True)


class CourseProgressSerializer(serializers.Serializer):
    """A student's aggregate progress through one course."""

    course_slug = serializers.CharField(read_only=True)
    course_title = serializers.CharField(read_only=True)
    enrollment_status = serializers.CharField(source="enrollment.status", read_only=True)
    enrolled_at = serializers.DateTimeField(source="enrollment.enrolled_at", read_only=True)
    completed_at = serializers.DateTimeField(read_only=True, allow_null=True)
    total_lessons = serializers.IntegerField(read_only=True)
    completed_lessons = serializers.IntegerField(read_only=True)
    percent = serializers.IntegerField(read_only=True)
    lessons = LessonProgressItemSerializer(many=True, read_only=True)


class MyCourseProgressSerializer(serializers.Serializer):
    """One course in the ``/me/progress/`` overview."""

    id = serializers.IntegerField(read_only=True)
    slug = serializers.CharField(read_only=True)
    title = serializers.CharField(read_only=True)
    completed_lessons = serializers.IntegerField(read_only=True)
    total_lessons = serializers.IntegerField(read_only=True)
    percentage = serializers.IntegerField(read_only=True)
    completed_at = serializers.DateTimeField(read_only=True, allow_null=True)
