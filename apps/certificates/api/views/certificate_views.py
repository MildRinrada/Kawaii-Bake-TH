"""Certificate and achievement endpoints.

Owner-scoped, with two deliberate public reads: the verification endpoint
(keyed only by an unguessable UUID token) and the badge catalogue, which
is presentation metadata about the platform rather than about any user.
"""

from __future__ import annotations

import uuid

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.certificates.api.serializers import (
    AchievementSerializer,
    BadgeSerializer,
    CertificateIssueSerializer,
    CertificateSerializer,
    CertificateVerificationSerializer,
)
from apps.certificates.selectors import badge_selector, certificate_selector
from apps.certificates.services import achievement_service, certificate_service
from apps.common.api.views import PaginatedServiceAPIView, ServiceAPIView


class CourseCertificateView(ServiceAPIView):
    """Request the caller's certificate for a completed course."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        request=CertificateIssueSerializer,
        responses={200: CertificateSerializer, 201: CertificateSerializer},
        tags=["certificates"],
    )
    def post(self, request: Request, slug: str) -> Response:
        """Issue (201) or return the existing certificate (200).

        The body carries the name to print, and only matters the first
        time an account asks: without a stored legal name the service
        answers 409 ``legal_name_required``, which is the client's cue to
        ask the learner and repeat the request.
        """
        serializer = CertificateIssueSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        certificate, created = certificate_service.issue_if_completed(
            user_id=request.user.id,
            course_slug=slug,
            viewer_is_staff=request.user.is_staff,
            first_name=serializer.validated_data["first_name"],
            last_name=serializer.validated_data["last_name"],
        )
        return Response(
            CertificateSerializer(certificate).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class MyCertificatesView(PaginatedServiceAPIView):
    """The caller's certificates, newest first  revoked included."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        responses={200: CertificateSerializer(many=True)}, tags=["certificates"]
    )
    def get(self, request: Request) -> Response:
        """Return a page of the caller's certificates."""
        queryset = certificate_selector.list_for_user(user_id=request.user.id)
        return self.paginated_response(queryset, CertificateSerializer)


class CertificateVerifyView(ServiceAPIView):
    """Public verification  for employers checking a printed certificate."""

    permission_classes = (AllowAny,)

    @extend_schema(
        responses={200: CertificateVerificationSerializer},
        tags=["certificates"],
    )
    def get(self, request: Request, verification_token: uuid.UUID) -> Response:
        """Return the certificate's public record and verdict."""
        certificate = certificate_service.verify_token(token=verification_token)
        return Response(
            CertificateVerificationSerializer(certificate).data,
            status=status.HTTP_200_OK,
        )


class MyAchievementsView(PaginatedServiceAPIView):
    """The caller's earned achievements."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        responses={200: AchievementSerializer(many=True)}, tags=["certificates"]
    )
    def get(self, request: Request) -> Response:
        """Return a page of the caller's achievements, newest first."""
        queryset = achievement_service.list_user(user_id=request.user.id)
        return self.paginated_response(queryset, AchievementSerializer)


class BadgeCatalogView(ServiceAPIView):
    """Every badge the platform presents  what there is to earn.

    Public and user-independent by construction: it answers "which
    achievements exist", never "who has them". A client pairs it with the
    owner-scoped ``/me/achievements/`` to show earned and locked side by
    side, which the earned ledger alone cannot express (ADR 0024).

    Unpaginated: the set is a small, curated, system-owned list.
    """

    permission_classes = (AllowAny,)

    @extend_schema(responses={200: BadgeSerializer(many=True)}, tags=["certificates"])
    def get(self, request: Request) -> Response:
        """Return every active badge definition."""
        badges = badge_selector.list_active()
        return Response(
            BadgeSerializer(badges, many=True).data, status=status.HTTP_200_OK
        )
