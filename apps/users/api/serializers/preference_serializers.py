"""Serializers for private user preferences."""

from __future__ import annotations

from rest_framework import serializers

from apps.common.api.serializers import StrictSerializer
from apps.users.constants import (
    MAX_DIETARY_RESTRICTIONS,
    WEEKLY_GOAL_MAX_MINUTES,
    WEEKLY_GOAL_MIN_MINUTES,
    BakingExperienceLevel,
    DietaryRestriction,
    PreferredLanguage,
    ProfileVisibility,
    Theme,
)


class UserPreferenceSerializer(serializers.Serializer):
    """The owner's privacy, learning and notification settings."""

    profile_visibility = serializers.CharField(read_only=True)
    show_birthday = serializers.BooleanField(read_only=True)
    show_location = serializers.BooleanField(read_only=True)

    preferred_difficulty = serializers.CharField(read_only=True)
    weekly_goal_minutes = serializers.IntegerField(read_only=True)
    dietary_restrictions = serializers.ListField(
        child=serializers.CharField(), read_only=True
    )

    theme = serializers.CharField(read_only=True)
    locale = serializers.CharField(read_only=True)

    email_course_updates = serializers.BooleanField(read_only=True)
    email_product_updates = serializers.BooleanField(read_only=True)
    email_marketing = serializers.BooleanField(read_only=True)


class UserPreferenceUpdateSerializer(StrictSerializer):
    """Validates a preferences PATCH payload. All fields optional."""

    profile_visibility = serializers.ChoiceField(
        choices=ProfileVisibility.choices, required=False
    )
    show_birthday = serializers.BooleanField(required=False)
    show_location = serializers.BooleanField(required=False)

    preferred_difficulty = serializers.ChoiceField(
        choices=BakingExperienceLevel.choices, required=False
    )
    weekly_goal_minutes = serializers.IntegerField(
        min_value=WEEKLY_GOAL_MIN_MINUTES,
        max_value=WEEKLY_GOAL_MAX_MINUTES,
        required=False,
    )
    dietary_restrictions = serializers.ListField(
        child=serializers.ChoiceField(choices=DietaryRestriction.choices),
        max_length=MAX_DIETARY_RESTRICTIONS,
        required=False,
    )

    theme = serializers.ChoiceField(choices=Theme.choices, required=False)
    locale = serializers.ChoiceField(
        choices=PreferredLanguage.choices, required=False
    )

    email_course_updates = serializers.BooleanField(required=False)
    email_product_updates = serializers.BooleanField(required=False)
    email_marketing = serializers.BooleanField(required=False)
