"""The reward endpoints: summary, history, claim, staff adjustment."""

from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.common.api.views import PaginatedServiceAPIView, ServiceAPIView
from apps.rewards.api.serializers import (
    AdjustmentSerializer,
    ClaimResultSerializer,
    RewardSummarySerializer,
    RewardTransactionSerializer,
    TransactionListQuerySerializer,
)
from apps.rewards.selectors import reward_selector
from apps.rewards.services import reward_service


class MyRewardsView(ServiceAPIView):
    """GET /me/rewards/ — the caller's balance and lifetime totals."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(responses={200: RewardSummarySerializer}, tags=["rewards"])
    def get(self, request: Request) -> Response:
        """Return the caller's reward summary (zeros before first earn)."""
        summary = reward_service.get_summary(user_id=request.user.id)
        return Response(RewardSummarySerializer(summary).data)


class MyRewardTransactionsView(PaginatedServiceAPIView):
    """GET /me/rewards/transactions/ — the caller's ledger, newest first."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[TransactionListQuerySerializer],
        responses={200: RewardTransactionSerializer(many=True)},
        tags=["rewards"],
    )
    def get(self, request: Request) -> Response:
        """Return a page of the caller's own reward history."""
        query = TransactionListQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        return self.paginated_response(
            reward_selector.list_transactions(user_id=request.user.id),
            RewardTransactionSerializer,
        )


class ClaimRewardsView(ServiceAPIView):
    """POST /me/rewards/claim/ — settle earnings up to current facts.

    The pull door of the economy, mirroring
    ``/me/gamification/recalculate/``: idempotent, monotonic, safe to
    call after any learning action or on page load. Replaying it cannot
    grant twice — every event is keyed and unique at the database.
    """

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        request=None, responses={200: ClaimResultSerializer}, tags=["rewards"]
    )
    def post(self, request: Request) -> Response:
        """Claim any unclaimed rewards; report what was settled."""
        result = reward_service.claim(user_id=request.user.id)
        return Response(ClaimResultSerializer(result).data)


class RewardAdjustmentView(ServiceAPIView):
    """POST /rewards/adjustments/ — staff-only balance correction."""

    permission_classes = (IsAdminUser,)

    @extend_schema(
        request=AdjustmentSerializer,
        responses={201: RewardTransactionSerializer},
        tags=["rewards"],
    )
    def post(self, request: Request) -> Response:
        """Apply an auditable, idempotent adjustment to a user's balance."""
        payload = AdjustmentSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        row = reward_service.adjust(
            target_username=payload.validated_data["username"],
            amount=payload.validated_data["amount"],
            reason=payload.validated_data["reason"],
            actor_handle=request.user.username,
            idempotency_key=payload.validated_data.get("idempotency_key", ""),
        )
        return Response(
            RewardTransactionSerializer(row).data, status=status.HTTP_201_CREATED
        )
