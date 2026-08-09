"""The public leaderboard, mounted at ``/api/v1/leaderboard/``."""

from __future__ import annotations

from django.urls import path

from apps.gamification.api.views.gamification_views import LeaderboardView

app_name = "gamification"

urlpatterns = [
    path("", LeaderboardView.as_view(), name="leaderboard"),
]
