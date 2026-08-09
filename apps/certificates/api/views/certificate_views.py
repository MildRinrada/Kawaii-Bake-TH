"""Certificate and achievement endpoints.

Everything is owner-scoped except the verification endpoint, which is the
one deliberately public read — keyed only by the unguessable UUID token.
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
    CertificateSerializer,
    CertificateVerificationSerializer,
)
from apps.certificates.selectors import certificate_selector
from apps.certificates.services import achievement_service, certificate_service
from apps.common.api.views import PaginatedServiceAPIView, ServiceAPIView


class CourseCertificateView(ServiceAPIView):
    """Request the caller's certificate for a completed course."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        request=None,
        responses={200: CertificateSerializer, 201: CertificateSerializer},
        tags=["certificates"],
    )
    def post(self, request: Request, slug: str) -> Response:
        """Issue (201) or return the existing certificate (200)."""
        certificate, created = certificate_service.issue_if_completed(
            user_id=request.user.id,
            course_slug=slug,
            viewer_is_staff=request.user.is_staff,
        )
        return Response(
            CertificateSerializer(certificate).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class MyCertificatesView(PaginatedServiceAPIView):
    """The caller's certificates, newest first — revoked included."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        responses={200: CertificateSerializer(many=True)}, tags=["certificates"]
    )
    def get(self, request: Request) -> Response:
        """Return a page of the caller's certificates."""
        queryset = certificate_selector.list_for_user(user_id=request.user.id)
        return self.paginated_response(queryset, CertificateSerializer)


class CertificateVerifyView(ServiceAPIView):
    """Public verification — for employers checking a printed certificate."""

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
