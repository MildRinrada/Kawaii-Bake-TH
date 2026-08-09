"""Read serializers for the question bank.

**This is the only module in the codebase allowed to render ``is_correct``.**
It serves the bank's private authoring surface, where every object has already
been ownership-filtered by the selector. Taker-facing payloads are built from
DTOs that have no such field (see ``selectors/question_selector.py``).
"""

from __future__ import annotations

from rest_framework import serializers


class OwnerChoiceSerializer(serializers.Serializer):
    """One answer choice, as seen by the question's author."""

    id = serializers.IntegerField(read_only=True)
    text = serializers.CharField(read_only=True)
    is_correct = serializers.BooleanField(read_only=True)
    position = serializers.IntegerField(read_only=True)


class QuestionTagSerializer(serializers.Serializer):
    """One tag reference."""

    name = serializers.CharField(read_only=True)
    slug = serializers.CharField(read_only=True)


class OwnerQuestionSerializer(serializers.Serializer):
    """One bank question, as seen by its author."""

    id = serializers.IntegerField(read_only=True)
    question_type = serializers.CharField(read_only=True)
    text = serializers.CharField(read_only=True)
    explanation = serializers.CharField(read_only=True)
    difficulty = serializers.CharField(read_only=True)
    version = serializers.IntegerField(read_only=True)
    supersedes_id = serializers.IntegerField(read_only=True, allow_null=True)
    frozen_at = serializers.DateTimeField(read_only=True, allow_null=True)
    is_frozen = serializers.BooleanField(read_only=True)
    choices = OwnerChoiceSerializer(many=True, read_only=True)
    tags = QuestionTagSerializer(many=True, read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
