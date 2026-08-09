"""The caller's gamification standing, mounted at ``/api/v1/me/`` by config.

Shares the ``me/`` prefix with progress, assistant and certificates by
config (ADR 0009); the patterns cannot collide.
"""

from __future__ import annotations

from django.urls import path

from apps.gamification.api.views.gamification_views import (
    MyGamificationView,
    MyStreakView,
    RecalculateGamificationView,
)

app_name = "my_gamification"

urlpatterns = [
    path("gamification/", MyGamificationView.as_view(), name="summary"),
    path(
        "gamification/recalculate/",
        RecalculateGamificationView.as_view(),
        name="recalculate",
    ),
    path("streak/", MyStreakView.as_view(), name="streak"),
]
