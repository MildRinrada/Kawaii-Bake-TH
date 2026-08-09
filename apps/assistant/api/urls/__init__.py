"""Assistant routes, mounted at ``/api/v1/assistant/``."""

from __future__ import annotations

from django.urls import path

from apps.assistant.api.views.assistant_views import (
    ConversationCreateView,
    ConversationDetailView,
    MessageCreateView,
)

app_name = "assistant"

urlpatterns = [
    path(
        "conversations/",
        ConversationCreateView.as_view(),
        name="conversation-create",
    ),
    path(
        "conversations/<int:conversation_id>/",
        ConversationDetailView.as_view(),
        name="conversation-detail",
    ),
    path(
        "conversations/<int:conversation_id>/messages/",
        MessageCreateView.as_view(),
        name="message-create",
    ),
]
