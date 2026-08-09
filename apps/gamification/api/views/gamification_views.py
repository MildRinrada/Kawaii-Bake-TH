"""Gamification endpoints.

The leaderboard is the one public read; everything else is the caller's
own standing. No business logic here — views assemble what the services
derive.
"""

from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.common.api.views import PaginatedServiceAPIView, ServiceAPIView
from apps.gamification.api.serializers import (
    GamificationSummarySerializer,
    LeaderboardEntrySerializer,
    StreakSerializer,
    XPTransactionSerializer,
)
from apps.gamification.constants import RECENT_TRANSACTIONS_LIMIT
from apps.gamification.selectors import gamification_selector
from apps.gamification.services import (
    leaderboard_service,
    level_service,
    streak_service,
    xp_service,
)


def _summary_payload(user_id: int) -> dict:
    """Assemble the summary body shared by the GET and the recalculate POST."""
    level = xp_service.get_level(user_id=user_id)
    streak = streak_service.get_streak(user_id=user_id)
    recent = gamification_selector.recent_transactions(
        user_id=user_id, limit=RECENT_TRANSACTIONS_LIMIT
    )
    return {
        "level": {
            "current_level": level.current_level,
            "current_xp": level.current_xp,
            # The curve lives in one place; clients render, never derive.
            "xp_for_next_level": level_service.xp_for_level(
                level=level.current_level
            ),
            "total_xp": level.total_xp,
        },
        "streak": StreakSerializer(streak).data,
        "recent_transactions": XPTransactionSerializer(recent, many=True).data,
    }


class MyGamificationView(ServiceAPIView):
    """The caller's level, streak and recent XP history."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        responses={200: GamificationSummarySerializer}, tags=["gamification"]
    )
    def get(self, request: Request) -> Response:
        """Return the stored standing (derived on first read)."""
        return Response(
            _summary_payload(request.user.id), status=status.HTTP_200_OK
        )


class RecalculateGamificationView(ServiceAPIView):
    """Rebuild the caller's XP and streak from the domains' current facts."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        request=None,
        responses={200: GamificationSummarySerializer},
        tags=["gamification"],
    )
    def post(self, request: Request) -> Response:
        """Reconcile the ledger and streak, then return the fresh summary."""
        xp_service.recalculate(user_id=request.user.id)
        streak_service.recalculate(user_id=request.user.id)
        return Response(
            _summary_payload(request.user.id), status=status.HTTP_200_OK
        )


class MyStreakView(ServiceAPIView):
    """The caller's streak standing."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(responses={200: StreakSerializer}, tags=["gamification"])
    def get(self, request: Request) -> Response:
        """Return current, longest and the last activity date."""
        streak = streak_service.get_streak(user_id=request.user.id)
        return Response(StreakSerializer(streak).data, status=status.HTTP_200_OK)


class LeaderboardView(PaginatedServiceAPIView):
    """The public leaderboard — handle, level, XP."""

    permission_classes = (AllowAny,)

    @extend_schema(
        responses={200: LeaderboardEntrySerializer(many=True)},
        tags=["gamification"],
    )
    def get(self, request: Request) -> Response:
        """Return a page of the top users by total XP."""
        return self.paginated_response(
            leaderboard_service.top_users(), LeaderboardEntrySerializer
        )
