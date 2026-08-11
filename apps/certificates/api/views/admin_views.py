"""Staff-only achievements endpoints: badge curation and the award ledger.

The ``admin/`` URL prefix is a naming convention, not the permission:
every view here declares ``IsAdminUser`` itself (ADR 0022), so a future
re-mount cannot accidentally expose them.
"""

from __future__ import annotations

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAdminUser
from rest_framework.request import Request
from rest_framework.response import Response

from apps.certificates.api.serializers.admin_serializers import (
    AdminAwardSerializer,
    AdminBadgeSerializer,
    AdminCertificateSerializer,
    AwardFilterSerializer,
    BadgeCreateSerializer,
    BadgeUpdateSerializer,
    CertificateFilterSerializer,
    CertificateRevokeSerializer,
)
from apps.certificates.selectors import award_selector, certificate_selector
from apps.certificates.services import badge_service, certificate_service
from apps.common.api.views import PaginatedServiceAPIView, ServiceAPIView


class AdminBadgeListView(ServiceAPIView):
    """List every badge definition and create new ones."""

    permission_classes = (IsAdminUser,)

    @extend_schema(
        responses={200: AdminBadgeSerializer(many=True)},
        tags=["achievements-admin"],
    )
    def get(self, request: Request) -> Response:
        """Return every badge, inactive included, with awarded counts.

        Unpaginated: the catalogue is a small, curated set.
        """
        badges = badge_service.list_badges()
        return Response(
            AdminBadgeSerializer(badges, many=True).data, status=status.HTTP_200_OK
        )

    @extend_schema(
        request=BadgeCreateSerializer,
        responses={201: AdminBadgeSerializer},
        tags=["achievements-admin"],
    )
    def post(self, request: Request) -> Response:
        """Create a badge definition.

        Creating a badge never awards it: awarding stays with the
        recalculation rules, so a new badge is presentation until a rule
        exists for it.
        """
        serializer = BadgeCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = dict(serializer.validated_data)
        badge = badge_service.create_badge(
            actor_id=request.user.id, slug=values.pop("slug"), **values
        )
        return Response(
            AdminBadgeSerializer(badge).data, status=status.HTTP_201_CREATED
        )


class AdminBadgeDetailView(ServiceAPIView):
    """Edit or delete one badge definition."""

    permission_classes = (IsAdminUser,)

    @extend_schema(
        request=BadgeUpdateSerializer,
        responses={200: AdminBadgeSerializer},
        tags=["achievements-admin"],
    )
    def patch(self, request: Request, slug: str) -> Response:
        """Apply a partial edit to a badge definition."""
        serializer = BadgeUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        badge = badge_service.update_badge(
            actor_id=request.user.id, slug=slug, changes=serializer.validated_data
        )
        return Response(AdminBadgeSerializer(badge).data, status=status.HTTP_200_OK)

    @extend_schema(responses={204: None}, tags=["achievements-admin"])
    def delete(self, request: Request, slug: str) -> Response:
        """Delete an unawarded badge; awarded ones must be deactivated."""
        badge_service.delete_badge(actor_id=request.user.id, slug=slug)
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminAwardListView(PaginatedServiceAPIView):
    """The cross-user award ledger, read-only.

    Awards are append-only facts (ADR 0012): staff can see who earned
    what, but there is deliberately no grant or revoke endpoint.
    """

    permission_classes = (IsAdminUser,)

    @extend_schema(
        parameters=[
            OpenApiParameter("search", str),
            OpenApiParameter("achievement_type", str),
        ],
        responses={200: AdminAwardSerializer(many=True)},
        tags=["achievements-admin"],
    )
    def get(self, request: Request) -> Response:
        """Return a page of awards, newest first."""
        filters = AwardFilterSerializer(data=request.query_params)
        filters.is_valid(raise_exception=True)
        values = filters.validated_data
        queryset = award_selector.list_awards(
            search=values.get("search", ""),
            achievement_type=values.get("achievement_type", ""),
        )
        return self.paginated_response(queryset, AdminAwardSerializer)


class AdminCertificateListView(PaginatedServiceAPIView):
    """The platform-wide certificate registry."""

    permission_classes = (IsAdminUser,)

    @extend_schema(
        parameters=[
            OpenApiParameter("search", str),
            OpenApiParameter("status", str),
        ],
        responses={200: AdminCertificateSerializer(many=True)},
        tags=["certificates-admin"],
    )
    def get(self, request: Request) -> Response:
        """Return a page of certificates, newest issuance first."""
        filters = CertificateFilterSerializer(data=request.query_params)
        filters.is_valid(raise_exception=True)
        values = filters.validated_data
        queryset = certificate_selector.list_all_certificates(
            search=values.get("search", ""),
            cert_status=values.get("status", ""),
            username=values.get("username", ""),
        )
        return self.paginated_response(queryset, AdminCertificateSerializer)


class AdminCertificateRevokeView(ServiceAPIView):
    """Withdraw one credential - attributable, reasoned, once."""

    permission_classes = (IsAdminUser,)

    @extend_schema(
        request=CertificateRevokeSerializer,
        responses={200: AdminCertificateSerializer},
        tags=["certificates-admin"],
    )
    def post(self, request: Request, certificate_id: int) -> Response:
        """Revoke the certificate, recording the actor and the reason.

        Raises:
            CertificateNotFoundError: If the certificate does not exist.
            CertificateAlreadyRevokedError: If it was already revoked -
                a conflict, so the first operator's reason stays.
        """
        serializer = CertificateRevokeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        certificate = certificate_service.revoke_as_staff(
            certificate_id=certificate_id,
            actor_id=request.user.id,
            reason=serializer.validated_data["reason"],
        )
        return Response(
            AdminCertificateSerializer(certificate).data, status=status.HTTP_200_OK
        )
