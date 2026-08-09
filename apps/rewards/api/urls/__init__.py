"""Staff reward routes, mounted at ``/api/v1/rewards/`` by config."""

from __future__ import annotations

from django.urls import path

from apps.rewards.api.views import RewardAdjustmentView

app_name = "rewards"

urlpatterns = [
    path("adjustments/", RewardAdjustmentView.as_view(), name="adjustments"),
]
