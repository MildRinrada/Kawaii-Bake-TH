"""The staff-only dashboard surface.

Reads are selectors, writes are services, and the views hold neither
querysets nor rules  the same shape as every other app. The only thing
special here is the permission class: ``IsAdminUser`` means ``is_staff``,
the same flag the frontend reads from ``/auth/me/`` to decide whether to
render an admin surface at all (ADR 0022).
"""

from __future__ import annotations

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAdminUser
from rest_framework.request import Request
from rest_framework.response import Response

from apps.common.api.views import PaginatedServiceAPIView, ServiceAPIView
from apps.security.api.serializers import (
    BlockRequestSerializer,
    EventFilterSerializer,
    ProfileFilterSerializer,
    ReviewRequestSerializer,
    SecurityEventSerializer,
    SecuritySummarySerializer,
    SecurityVocabularySerializer,
    ThreatProfileDetailSerializer,
    ThreatProfileSerializer,
)
from apps.security.constants import ReviewState, SignalKind, ThreatLevel
from apps.security.exceptions import ThreatProfileNotFoundError
from apps.security.selectors import threat_selector
from apps.security.services import threat_service


class SecuritySummaryView(ServiceAPIView):
    """Headline counters for the dashboard's top strip."""

    permission_classes = (IsAdminUser,)

    @extend_schema(responses={200: SecuritySummarySerializer}, tags=["security-admin"])
    def get(self, request: Request) -> Response:
        """Return live totals, per-band counts and the top offenders."""
        return Response(threat_selector.summary(), status=status.HTTP_200_OK)


class SecurityVocabularyView(ServiceAPIView):
    """The label vocabulary the dashboard's filters render from."""

    permission_classes = (IsAdminUser,)

    @extend_schema(
        responses={200: SecurityVocabularySerializer}, tags=["security-admin"]
    )
    def get(self, request: Request) -> Response:
        """Return every signal kind, level and review state with its label."""
        return Response(
            {
                "kinds": [
                    {"value": value, "label": label}
                    for value, label in SignalKind.choices
                ],
                "levels": [
                    {"value": value, "label": label}
                    for value, label in ThreatLevel.choices
                ],
                "review_states": [
                    {"value": value, "label": label}
                    for value, label in ReviewState.choices
                ],
            },
            status=status.HTTP_200_OK,
        )


class SecurityEventListView(PaginatedServiceAPIView):
    """The append-only event log."""

    permission_classes = (IsAdminUser,)

    @extend_schema(
        parameters=[
            OpenApiParameter("kind", str),
            OpenApiParameter("severity", str),
            OpenApiParameter("ip", str),
            OpenApiParameter("search", str),
            OpenApiParameter("since_hours", int),
        ],
        responses={200: SecurityEventSerializer(many=True)},
        tags=["security-admin"],
    )
    def get(self, request: Request) -> Response:
        """Return a page of events, newest first."""
        filters = EventFilterSerializer(data=request.query_params)
        filters.is_valid(raise_exception=True)
        values = filters.validated_data
        queryset = threat_selector.list_events(
            kind=values.get("kind", ""),
            severity=values.get("severity", ""),
            ip=values.get("ip", ""),
            search=values.get("search", ""),
            since_hours=values.get("since_hours"),
        )
        return self.paginated_response(queryset, SecurityEventSerializer)


class ThreatProfileListView(PaginatedServiceAPIView):
    """Offender profiles, worst first."""

    permission_classes = (IsAdminUser,)

    @extend_schema(
        parameters=[
            OpenApiParameter("level", str),
            OpenApiParameter("review_state", str),
            OpenApiParameter("blocked", bool),
            OpenApiParameter("search", str),
            OpenApiParameter("ordering", str),
        ],
        responses={200: ThreatProfileSerializer(many=True)},
        tags=["security-admin"],
    )
    def get(self, request: Request) -> Response:
        """Return a page of profiles."""
        filters = ProfileFilterSerializer(data=request.query_params)
        filters.is_valid(raise_exception=True)
        values = filters.validated_data
        queryset = threat_selector.list_profiles(
            level=values.get("level", ""),
            review_state=values.get("review_state", ""),
            blocked=values.get("blocked"),
            search=values.get("search", ""),
            ordering=values.get("ordering") or "-score",
        )
        return self.paginated_response(queryset, ThreatProfileSerializer)


class ThreatProfileDetailView(ServiceAPIView):
    """One offender with the evidence behind its score."""

    permission_classes = (IsAdminUser,)

    @extend_schema(
        responses={200: ThreatProfileDetailSerializer}, tags=["security-admin"]
    )
    def get(self, request: Request, profile_id: int) -> Response:
        """Return the profile plus its most recent events.

        Raises:
            ThreatProfileNotFoundError: If the profile does not exist.
        """
        profile = threat_selector.get_profile(profile_id=profile_id)
        if profile is None:
            raise ThreatProfileNotFoundError()
        data = ThreatProfileDetailSerializer(profile).data
        data["recent_events"] = SecurityEventSerializer(
            threat_selector.recent_events_for_ip(ip=profile.ip), many=True
        ).data
        return Response(data, status=status.HTTP_200_OK)


class ThreatProfileBlockView(ServiceAPIView):
    """Block or unblock one address."""

    permission_classes = (IsAdminUser,)

    @extend_schema(
        request=BlockRequestSerializer,
        responses={200: ThreatProfileSerializer},
        tags=["security-admin"],
    )
    def post(self, request: Request, profile_id: int) -> Response:
        """Start a time-boxed block."""
        serializer = BlockRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile = threat_service.block(
            profile_id=profile_id,
            minutes=serializer.validated_data["minutes"],
            actor_id=request.user.id,
        )
        return Response(ThreatProfileSerializer(profile).data, status=status.HTTP_200_OK)

    @extend_schema(responses={200: ThreatProfileSerializer}, tags=["security-admin"])
    def delete(self, request: Request, profile_id: int) -> Response:
        """Lift a block immediately."""
        profile = threat_service.unblock(
            profile_id=profile_id, actor_id=request.user.id
        )
        return Response(ThreatProfileSerializer(profile).data, status=status.HTTP_200_OK)


class ThreatProfileReviewView(ServiceAPIView):
    """Record a triage decision."""

    permission_classes = (IsAdminUser,)

    @extend_schema(
        request=ReviewRequestSerializer,
        responses={200: ThreatProfileSerializer},
        tags=["security-admin"],
    )
    def post(self, request: Request, profile_id: int) -> Response:
        """Move the profile out of the review queue.

        Changes no score and deletes no evidence; fresh activity puts the
        profile straight back in the queue.
        """
        serializer = ReviewRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile = threat_service.review(
            profile_id=profile_id,
            state=serializer.validated_data["state"],
            actor_id=request.user.id,
            note=serializer.validated_data.get("note", ""),
        )
        return Response(ThreatProfileSerializer(profile).data, status=status.HTTP_200_OK)
