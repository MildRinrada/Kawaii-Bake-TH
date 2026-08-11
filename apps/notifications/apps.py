"""App configuration for the notifications app."""

from __future__ import annotations

from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    """The in-app notification center  an event-time push sink.

    The mirror image of gamification (ADR 0015): where that app *pulls*
    derived aggregates, this one is *pushed* event-time facts by producer
    services (reviews, courses, certificates) calling its public service
    after their own transactions commit. This app imports no content
    domain, holds no FK to any content, and delivers best-effort  a
    notification failure is logged and swallowed, never surfaced to the
    producer. See ``docs/adr/0016-notifications-as-a-push-sink.md``.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.notifications"
    label = "notifications"
    verbose_name = "Notifications"
