"""Serializers for assistant payloads.

Read serializers are plain field maps over model instances; write
serializers are :class:`StrictSerializer` (unknown keys rejected) and are
never model-backed — writes go through services (Architecture.md DRF rules).
"""

from __future__ import annotations

from rest_framework import serializers

from apps.assistant.constants import (
    MESSAGE_MAX_LENGTH,
    AssistantLanguage,
    ContextType,
)
from apps.common.api.serializers import StrictSerializer


class ConversationCreateSerializer(StrictSerializer):
    """Payload for opening a conversation.

    The id/context-type cross-check lives in the service (it must hold for
    every caller, not just HTTP); this layer validates shape only.
    """

    language = serializers.ChoiceField(
        choices=AssistantLanguage.choices, default=AssistantLanguage.TH
    )
    context_type = serializers.ChoiceField(
        choices=ContextType.choices, default=ContextType.GENERAL
    )
    recipe_id = serializers.IntegerField(required=False, min_value=1)
    lesson_id = serializers.IntegerField(required=False, min_value=1)
    course_id = serializers.IntegerField(required=False, min_value=1)


class MessageCreateSerializer(StrictSerializer):
    """Payload for sending one user message."""

    content = serializers.CharField(max_length=MESSAGE_MAX_LENGTH)


class MessageSerializer(serializers.Serializer):
    """One transcript turn."""

    id = serializers.IntegerField(read_only=True)
    role = serializers.CharField(read_only=True)
    content = serializers.CharField(read_only=True)
    provider = serializers.CharField(read_only=True)
    model_name = serializers.CharField(read_only=True)
    token_input = serializers.IntegerField(read_only=True, allow_null=True)
    token_output = serializers.IntegerField(read_only=True, allow_null=True)
    created_at = serializers.DateTimeField(read_only=True)


class ConversationSerializer(serializers.Serializer):
    """A conversation row — list and creation payloads."""

    id = serializers.IntegerField(read_only=True)
    title = serializers.CharField(read_only=True)
    language = serializers.CharField(read_only=True)
    context_type = serializers.CharField(read_only=True)
    recipe_id = serializers.IntegerField(read_only=True, allow_null=True)
    lesson_id = serializers.IntegerField(read_only=True, allow_null=True)
    course_id = serializers.IntegerField(read_only=True, allow_null=True)
    prompt_version = serializers.CharField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)


class _PaginatedMessagesSerializer(serializers.Serializer):
    """Schema shape of the embedded message page (docs only)."""

    count = serializers.IntegerField(read_only=True)
    next = serializers.CharField(read_only=True, allow_null=True)
    previous = serializers.CharField(read_only=True, allow_null=True)
    results = MessageSerializer(many=True, read_only=True)


class ConversationDetailSerializer(serializers.Serializer):
    """Schema shape of the history endpoint (docs only).

    The view assembles this response by hand — the conversation from the
    service, the message page from the paginator — so this serializer exists
    for drf-spectacular, not for serialisation.
    """

    conversation = ConversationSerializer(read_only=True)
    messages = _PaginatedMessagesSerializer(read_only=True)
