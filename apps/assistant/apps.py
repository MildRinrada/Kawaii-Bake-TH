"""App configuration for the assistant app."""

from __future__ import annotations

from django.apps import AppConfig


class AssistantConfig(AppConfig):
    """Thai-first AI assistant conversations.

    Owns AI conversation state (conversations, messages, prompt templates,
    usage logs) and nothing else: content context is read through the content
    apps' public selectors/services, and the AI backends live behind the
    framework-free ``ai`` package — the assistant never knows which provider
    is answering. Content apps never import this app.
    See ``docs/adr/0013-ai-assistant-foundation.md``.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.assistant"
    label = "assistant"
    verbose_name = "AI Assistant"
