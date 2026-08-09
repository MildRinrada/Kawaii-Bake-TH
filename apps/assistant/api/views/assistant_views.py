"""Assistant endpoints.

Every endpoint requires authentication — anonymous conversations are not
supported in this phase — and every conversation lookup is owner-scoped by
the service, so "someone else's conversation" is indistinguishable from
"no such conversation" (404).
"""

from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.assistant.api.serializers import (
    ConversationCreateSerializer,
    ConversationDetailSerializer,
    ConversationSerializer,
    MessageCreateSerializer,
    MessageSerializer,
)
from apps.assistant.selectors import conversation_selector
from apps.assistant.services import conversation_service, message_service
from apps.common.api.views import PaginatedServiceAPIView, ServiceAPIView


class ConversationCreateView(ServiceAPIView):
    """Open a conversation, optionally anchored to content."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        request=ConversationCreateSerializer,
        responses={201: ConversationSerializer},
        tags=["assistant"],
    )
    def post(self, request: Request) -> Response:
        """Create a conversation for the caller."""
        serializer = ConversationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        conversation = conversation_service.create_conversation(
            user_id=request.user.id,
            viewer_is_staff=request.user.is_staff,
            language=data["language"],
            context_type=data["context_type"],
            recipe_id=data.get("recipe_id"),
            lesson_id=data.get("lesson_id"),
            course_id=data.get("course_id"),
        )
        return Response(
            ConversationSerializer(conversation).data,
            status=status.HTTP_201_CREATED,
        )


class ConversationDetailView(PaginatedServiceAPIView):
    """One conversation with a page of its transcript."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        responses={200: ConversationDetailSerializer}, tags=["assistant"]
    )
    def get(self, request: Request, conversation_id: int) -> Response:
        """Return the conversation and its messages, oldest first."""
        conversation = conversation_service.require_owned_conversation(
            conversation_id=conversation_id, user_id=request.user.id
        )
        queryset = conversation_selector.list_messages(
            conversation_id=conversation.pk
        )
        page = self.paginator.paginate_queryset(queryset, request, view=self)
        messages = self.paginator.get_paginated_response(
            MessageSerializer(page, many=True).data
        ).data
        return Response(
            {
                "conversation": ConversationSerializer(conversation).data,
                "messages": messages,
            },
            status=status.HTTP_200_OK,
        )


class MessageCreateView(ServiceAPIView):
    """Send a message and receive the assistant's reply."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        request=MessageCreateSerializer,
        responses={201: MessageSerializer},
        tags=["assistant"],
    )
    def post(self, request: Request, conversation_id: int) -> Response:
        """Append the user's message; return the assistant's turn."""
        serializer = MessageCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        reply = message_service.send_message(
            user_id=request.user.id,
            conversation_id=conversation_id,
            content=serializer.validated_data["content"],
            viewer_is_staff=request.user.is_staff,
        )
        return Response(
            MessageSerializer(reply).data, status=status.HTTP_201_CREATED
        )


class MyConversationsView(PaginatedServiceAPIView):
    """The caller's conversations, most recently active first."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        responses={200: ConversationSerializer(many=True)}, tags=["assistant"]
    )
    def get(self, request: Request) -> Response:
        """Return a page of the caller's conversations."""
        queryset = conversation_selector.list_for_user(user_id=request.user.id)
        return self.paginated_response(queryset, ConversationSerializer)
