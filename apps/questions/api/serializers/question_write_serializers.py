"""Write serializers for the question bank."""

from __future__ import annotations

from rest_framework import serializers

from apps.common.api.serializers import (
    CommaSeparatedCharField,
    CommaSeparatedChoiceField,
    StrictSerializer,
)
from apps.questions.constants import (
    CHOICE_TEXT_MAX_LENGTH,
    EXPLANATION_MAX_LENGTH,
    MAX_CHOICES_PER_QUESTION,
    MAX_TAGS_PER_QUESTION,
    QUESTION_TEXT_MAX_LENGTH,
    QUESTION_TEXT_MIN_LENGTH,
    TAG_NAME_MAX_LENGTH,
    QuestionDifficulty,
    QuestionScope,
    QuestionType,
)


class ChoiceInputSerializer(StrictSerializer):
    """One submitted answer choice."""

    text = serializers.CharField(max_length=CHOICE_TEXT_MAX_LENGTH)
    is_correct = serializers.BooleanField(default=False)


class QuestionCreateSerializer(StrictSerializer):
    """Validates a question creation payload.

    Message shape only — the per-type choice rules (correct-answer counts,
    duplicates, true/false arity) are domain rules and live in
    ``validators/question_validator.py``.
    """

    question_type = serializers.ChoiceField(choices=QuestionType.choices)
    text = serializers.CharField(
        min_length=QUESTION_TEXT_MIN_LENGTH, max_length=QUESTION_TEXT_MAX_LENGTH
    )
    explanation = serializers.CharField(
        max_length=EXPLANATION_MAX_LENGTH, required=False, allow_blank=True
    )
    difficulty = serializers.ChoiceField(
        choices=QuestionDifficulty.choices, required=False
    )
    choices = ChoiceInputSerializer(many=True, max_length=MAX_CHOICES_PER_QUESTION)
    tags = serializers.ListField(
        child=serializers.CharField(max_length=TAG_NAME_MAX_LENGTH),
        required=False,
        max_length=MAX_TAGS_PER_QUESTION,
    )


class QuestionUpdateSerializer(StrictSerializer):
    """Validates a partial question update; absent means unchanged."""

    question_type = serializers.ChoiceField(
        choices=QuestionType.choices, required=False
    )
    text = serializers.CharField(
        min_length=QUESTION_TEXT_MIN_LENGTH,
        max_length=QUESTION_TEXT_MAX_LENGTH,
        required=False,
    )
    explanation = serializers.CharField(
        max_length=EXPLANATION_MAX_LENGTH, required=False, allow_blank=True
    )
    difficulty = serializers.ChoiceField(
        choices=QuestionDifficulty.choices, required=False
    )
    choices = ChoiceInputSerializer(
        many=True, required=False, max_length=MAX_CHOICES_PER_QUESTION
    )
    tags = serializers.ListField(
        child=serializers.CharField(max_length=TAG_NAME_MAX_LENGTH),
        required=False,
        max_length=MAX_TAGS_PER_QUESTION,
    )


class QuestionListQuerySerializer(StrictSerializer):
    """Validates the query string of a bank listing."""

    type = CommaSeparatedChoiceField(
        required=False, allow_blank=True, choices=QuestionType.choices
    )
    difficulty = CommaSeparatedChoiceField(
        required=False, allow_blank=True, choices=QuestionDifficulty.choices
    )
    tag = CommaSeparatedCharField(required=False, allow_blank=True)
    search = serializers.CharField(required=False, allow_blank=True, max_length=100)
    scope = serializers.ChoiceField(choices=QuestionScope.choices, required=False)
    page = serializers.IntegerField(required=False, min_value=1)
    page_size = serializers.IntegerField(required=False, min_value=1)
