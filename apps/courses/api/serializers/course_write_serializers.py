"""Write serializers for courses.

``status`` is deliberately absent from both: publishing goes through the
dedicated transition endpoints, which run the completeness checks.
"""

from __future__ import annotations

from rest_framework import serializers

from apps.common.api.serializers import (
    CommaSeparatedCharField,
    CommaSeparatedChoiceField,
    StrictSerializer,
)
from apps.courses.constants import (
    COURSE_SUMMARY_MAX_LENGTH,
    COURSE_TITLE_MAX_LENGTH,
    COURSE_TITLE_MIN_LENGTH,
    MAX_CATEGORIES_PER_COURSE,
    CourseDifficulty,
    CourseOrdering,
    CourseScope,
    CourseVisibility,
)


class CourseCreateSerializer(StrictSerializer):
    """Validates a course creation payload."""

    title = serializers.CharField(
        min_length=COURSE_TITLE_MIN_LENGTH, max_length=COURSE_TITLE_MAX_LENGTH
    )
    summary = serializers.CharField(
        max_length=COURSE_SUMMARY_MAX_LENGTH, required=False, allow_blank=True
    )
    description = serializers.CharField(required=False, allow_blank=True)
    difficulty = serializers.ChoiceField(
        choices=CourseDifficulty.choices, required=False
    )
    visibility = serializers.ChoiceField(
        choices=CourseVisibility.choices, required=False
    )
    thumbnail = serializers.ImageField(required=False, allow_null=True)
    category_slugs = serializers.ListField(
        child=serializers.CharField(max_length=80),
        required=False,
        max_length=MAX_CATEGORIES_PER_COURSE,
    )


class CourseUpdateSerializer(StrictSerializer):
    """Validates a partial course update; absent means unchanged."""

    title = serializers.CharField(
        min_length=COURSE_TITLE_MIN_LENGTH,
        max_length=COURSE_TITLE_MAX_LENGTH,
        required=False,
    )
    slug = serializers.SlugField(allow_unicode=True, required=False)
    summary = serializers.CharField(
        max_length=COURSE_SUMMARY_MAX_LENGTH, required=False, allow_blank=True
    )
    description = serializers.CharField(required=False, allow_blank=True)
    difficulty = serializers.ChoiceField(
        choices=CourseDifficulty.choices, required=False
    )
    visibility = serializers.ChoiceField(
        choices=CourseVisibility.choices, required=False
    )
    thumbnail = serializers.ImageField(required=False, allow_null=True)
    category_slugs = serializers.ListField(
        child=serializers.CharField(max_length=80),
        required=False,
        max_length=MAX_CATEGORIES_PER_COURSE,
    )


class CourseListQuerySerializer(StrictSerializer):
    """Validates the query string of a course listing.

    ``page`` / ``page_size`` are declared so the strict check does not reject
    them; the paginator reads them from the request itself.
    """

    search = serializers.CharField(required=False, allow_blank=True, max_length=100)
    category = CommaSeparatedCharField(
        required=False, allow_blank=True, max_items=MAX_CATEGORIES_PER_COURSE
    )
    difficulty = CommaSeparatedChoiceField(
        required=False, allow_blank=True, choices=CourseDifficulty.choices
    )
    instructor = serializers.CharField(required=False, allow_blank=True, max_length=30)
    ordering = serializers.ChoiceField(choices=CourseOrdering.choices, required=False)
    scope = serializers.ChoiceField(choices=CourseScope.choices, required=False)
    page = serializers.IntegerField(required=False, min_value=1)
    page_size = serializers.IntegerField(required=False, min_value=1)
