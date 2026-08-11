"""Write serializers for quizzes.

``status`` is deliberately absent: publishing goes through the dedicated
transition endpoints, which run the completeness checks.
"""

from __future__ import annotations

from rest_framework import serializers

from apps.common.api.serializers import StrictSerializer
from apps.quizzes.constants import (
    MAX_QUESTIONS_PER_QUIZ,
    QUIZ_TITLE_MAX_LENGTH,
    QUIZ_TITLE_MIN_LENGTH,
    QuizOrdering,
    QuizScope,
    QuizVisibility,
)


class QuizCreateSerializer(StrictSerializer):
    """Validates a quiz creation payload."""

    title = serializers.CharField(
        min_length=QUIZ_TITLE_MIN_LENGTH, max_length=QUIZ_TITLE_MAX_LENGTH
    )
    description = serializers.CharField(required=False, allow_blank=True)
    pass_percent = serializers.IntegerField(
        required=False, min_value=0, max_value=100
    )
    visibility = serializers.ChoiceField(
        choices=QuizVisibility.choices, required=False
    )
    question_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        max_length=MAX_QUESTIONS_PER_QUIZ,
    )


class QuizUpdateSerializer(StrictSerializer):
    """Validates a partial quiz update; absent means unchanged.

    ``question_ids`` replaces the whole composition in submitted order 
    reordering is this same operation.
    """

    title = serializers.CharField(
        min_length=QUIZ_TITLE_MIN_LENGTH,
        max_length=QUIZ_TITLE_MAX_LENGTH,
        required=False,
    )
    slug = serializers.SlugField(allow_unicode=True, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    pass_percent = serializers.IntegerField(
        required=False, min_value=0, max_value=100
    )
    visibility = serializers.ChoiceField(
        choices=QuizVisibility.choices, required=False
    )
    question_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        max_length=MAX_QUESTIONS_PER_QUIZ,
    )


class QuizListQuerySerializer(StrictSerializer):
    """Validates the query string of a quiz listing."""

    owner = serializers.CharField(required=False, allow_blank=True, max_length=30)
    ordering = serializers.ChoiceField(choices=QuizOrdering.choices, required=False)
    scope = serializers.ChoiceField(choices=QuizScope.choices, required=False)
    page = serializers.IntegerField(required=False, min_value=1)
    page_size = serializers.IntegerField(required=False, min_value=1)


class AnswerInputSerializer(StrictSerializer):
    """One submitted answer: a question and the selected choice ids."""

    question_id = serializers.IntegerField(min_value=1)
    choice_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=True,
    )


class QuizSubmitSerializer(StrictSerializer):
    """Validates a submission payload.

    Message shape only  matching the attempt snapshot (unknown ids, choices
    belonging to the question) is domain validation in the attempt service.
    """

    answers = AnswerInputSerializer(many=True, allow_empty=True)
