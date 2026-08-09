"""The caller's conversation list, mounted at ``/api/v1/me/`` by config.

The shared prefix is a config concern, not app coupling (ADR 0009); the
``assistant/…`` patterns cannot collide with the progress app's ``progress/``.
"""

from __future__ import annotations

from django.urls import path

from apps.assistant.api.views.assistant_views import MyConversationsView

app_name = "my_assistant"

urlpatterns = [
    path(
        "assistant/conversations/",
        MyConversationsView.as_view(),
        name="conversations",
    ),
]
