"""Serializers for lessons and progress."""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.common.api.serializers import StrictSerializer
from apps.lessons.constants import (
    LESSON_CONTENT_MAX_LENGTH,
    LESSON_TITLE_MAX_LENGTH,
    LESSON_TITLE_MIN_LENGTH,
    VideoProvider,
)


class LessonSyllabusItemSerializer(serializers.Serializer):
    """One lesson on the public syllabus — metadata only, never content."""

    id = serializers.IntegerField(read_only=True)
    title = serializers.CharField(read_only=True)
    position = serializers.IntegerField(read_only=True)
    duration_minutes = serializers.IntegerField(read_only=True)
    is_preview = serializers.BooleanField(read_only=True)
    status = serializers.CharField(read_only=True)
    has_video = serializers.SerializerMethodField()

    def get_has_video(self, obj: Any) -> bool:
        """Whether the lesson carries a video, without exposing the URL."""
        return bool(obj.video_url)


class LessonDetailSerializer(serializers.Serializer):
    """A full lesson, returned only once the content gate has passed."""

    id = serializers.IntegerField(read_only=True)
    course_slug = serializers.CharField(source="course.slug", read_only=True)
    course_title = serializers.CharField(source="course.title", read_only=True)
    title = serializers.CharField(read_only=True)
    content = serializers.CharField(read_only=True)
    position = serializers.IntegerField(read_only=True)
    duration_minutes = serializers.IntegerField(read_only=True)
    is_preview = serializers.BooleanField(read_only=True)
    status = serializers.CharField(read_only=True)
    video_url = serializers.CharField(read_only=True)
    video_provider = serializers.CharField(read_only=True)
    video_duration_seconds = serializers.IntegerField(read_only=True, allow_null=True)
    recipe = serializers.SerializerMethodField()
    quiz = serializers.SerializerMethodField()

    def get_recipe(self, obj: Any) -> dict[str, Any] | None:
        """Return the linked recipe reference, redacted for this viewer.

        Provided by the view via context after a viewer-aware lookup; a recipe
        that has gone private since linking degrades to ``None`` — never a leak.
        """
        return self.context.get("recipe_ref")

    def get_quiz(self, obj: Any) -> dict[str, Any] | None:
        """Return the linked quiz reference, redacted for this viewer.

        Same degradation contract as the recipe: a quiz hidden from this
        viewer serializes as ``None`` rather than leaking its existence.
        """
        return self.context.get("quiz_ref")


class LessonCreateSerializer(StrictSerializer):
    """Validates a lesson creation payload."""

    title = serializers.CharField(
        min_length=LESSON_TITLE_MIN_LENGTH, max_length=LESSON_TITLE_MAX_LENGTH
    )
    content = serializers.CharField(
        max_length=LESSON_CONTENT_MAX_LENGTH, required=False, allow_blank=True
    )
    duration_minutes = serializers.IntegerField(required=False, min_value=0, default=0)
    is_preview = serializers.BooleanField(required=False, default=False)
    video_url = serializers.URLField(required=False, allow_blank=True)
    video_provider = serializers.ChoiceField(
        choices=VideoProvider.choices, required=False, allow_blank=True
    )
    video_duration_seconds = serializers.IntegerField(
        required=False, allow_null=True, min_value=0
    )
    recipe_id = serializers.IntegerField(required=False, allow_null=True)
    quiz_id = serializers.IntegerField(required=False, allow_null=True)


class LessonUpdateSerializer(StrictSerializer):
    """Validates a partial lesson update.

    ``status`` is editable here — lessons have no completeness gate of their
    own; publishing a lesson simply puts it on the syllabus and updates the
    course's counter through the repository choke point.
    """

    title = serializers.CharField(
        min_length=LESSON_TITLE_MIN_LENGTH,
        max_length=LESSON_TITLE_MAX_LENGTH,
        required=False,
    )
    content = serializers.CharField(
        max_length=LESSON_CONTENT_MAX_LENGTH, required=False, allow_blank=True
    )
    duration_minutes = serializers.IntegerField(required=False, min_value=0)
    is_preview = serializers.BooleanField(required=False)
    status = serializers.ChoiceField(
        choices=[("draft", "draft"), ("published", "published")], required=False
    )
    video_url = serializers.URLField(required=False, allow_blank=True)
    video_provider = serializers.ChoiceField(
        choices=VideoProvider.choices, required=False, allow_blank=True
    )
    video_duration_seconds = serializers.IntegerField(
        required=False, allow_null=True, min_value=0
    )
    recipe_id = serializers.IntegerField(required=False, allow_null=True)
    quiz_id = serializers.IntegerField(required=False, allow_null=True)


class LessonReorderSerializer(StrictSerializer):
    """Validates a reorder payload."""

    lesson_ids = serializers.ListField(
        child=serializers.IntegerField(), allow_empty=False, max_length=100
    )


