"""Serializers for Q&A payloads.

One public shape per endpoint; authors appear as public handles only.
"""

from __future__ import annotations

from rest_framework import serializers

from apps.common.api.serializers import StrictSerializer
from apps.qa.constants import (
    ANSWER_BODY_MAX_LENGTH,
    THREAD_BODY_MAX_LENGTH,
    THREAD_MODERATION_CHOICES,
    THREAD_TITLE_MAX_LENGTH,
    ThreadTargetKind,
)


class AnswerSerializer(serializers.Serializer):
    """One answer."""

    id = serializers.IntegerField(read_only=True)
    author_handle = serializers.CharField(read_only=True, source="author.username")
    body = serializers.CharField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)


class _TargetRefSerializer(serializers.Serializer):
    """The asked-about content, as a card link."""

    id = serializers.IntegerField(read_only=True)
    slug = serializers.CharField(read_only=True)
    title = serializers.CharField(read_only=True)


class ThreadSerializer(serializers.Serializer):
    """A question thread  list and detail share this shape."""

    id = serializers.IntegerField(read_only=True)
    author_handle = serializers.CharField(read_only=True, source="author.username")
    title = serializers.CharField(read_only=True)
    body = serializers.CharField(read_only=True)
    status = serializers.CharField(read_only=True)
    recipe = _TargetRefSerializer(read_only=True, allow_null=True)
    course = _TargetRefSerializer(read_only=True, allow_null=True)
    accepted_answer = AnswerSerializer(read_only=True, allow_null=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
    # Annotated by the selector, never stored  the three numbers a
    # reader uses to choose a thread. Every read goes through
    # ``qa_selector``, so they are always present.
    answer_count = serializers.IntegerField(read_only=True)
    view_count = serializers.IntegerField(read_only=True)
    last_answer_at = serializers.DateTimeField(read_only=True, allow_null=True)


class ThreadCreateSerializer(StrictSerializer):
    """Payload for asking a question."""

    target_type = serializers.ChoiceField(choices=ThreadTargetKind.choices)
    target_slug = serializers.CharField(max_length=220)
    title = serializers.CharField(max_length=THREAD_TITLE_MAX_LENGTH)
    body = serializers.CharField(
        max_length=THREAD_BODY_MAX_LENGTH, required=False, allow_blank=True
    )


class ThreadUpdateSerializer(StrictSerializer):
    """Payload for editing a thread; ``status`` is staff moderation."""

    title = serializers.CharField(
        max_length=THREAD_TITLE_MAX_LENGTH, required=False
    )
    body = serializers.CharField(
        max_length=THREAD_BODY_MAX_LENGTH, required=False, allow_blank=True
    )
    status = serializers.ChoiceField(
        choices=THREAD_MODERATION_CHOICES, required=False
    )


class AnswerCreateSerializer(StrictSerializer):
    """Payload for answering (and for editing an answer)."""

    body = serializers.CharField(max_length=ANSWER_BODY_MAX_LENGTH)


class AcceptAnswerSerializer(StrictSerializer):
    """Payload for marking the accepted answer."""

    answer_id = serializers.IntegerField(min_value=1)
