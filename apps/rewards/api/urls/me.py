"""The caller's reward routes, mounted at ``/api/v1/me/`` by config.

Shares the ``me/`` prefix with progress, assistant, certificates and
gamification by config (ADR 0009); the patterns cannot collide.
"""

from __future__ import annotations

from django.urls import path

from apps.rewards.api.views import (
    ClaimRewardsView,
    MyRewardsView,
    MyRewardTransactionsView,
)

app_name = "my_rewards"

urlpatterns = [
    path("rewards/", MyRewardsView.as_view(), name="summary"),
    path(
        "rewards/transactions/",
        MyRewardTransactionsView.as_view(),
        name="transactions",
    ),
    path("rewards/claim/", ClaimRewardsView.as_view(), name="claim"),
]
