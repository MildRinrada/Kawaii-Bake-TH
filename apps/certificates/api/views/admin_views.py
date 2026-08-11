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
    TemplateDetailSerializer,
    TemplateDraftSerializer,
    TemplateRowSerializer,
)
from apps.certificates.selectors import award_selector, certificate_selector
from apps.certificates.services import (
    badge_service,
    certificate_service,
    template_service,
)
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


class AdminTemplateListView(ServiceAPIView):
    """Existing template rows, for the designer workspace."""

    permission_classes = (IsAdminUser,)

    @extend_schema(
        responses={200: TemplateRowSerializer(many=True)},
        tags=["certificates-admin"],
    )
    def get(self, request: Request) -> Response:
        """Return every course that has a template row.

        Courses without a row use the built-in default design; the
        frontend merges this with the course list to show that honestly.
        """
        rows = template_service.list_templates()
        return Response(
            TemplateRowSerializer(rows, many=True).data, status=status.HTTP_200_OK
        )


class AdminTemplateDetailView(ServiceAPIView):
    """One course's design documents: read, autosave, remove."""

    permission_classes = (IsAdminUser,)

    @extend_schema(
        responses={200: TemplateDetailSerializer}, tags=["certificates-admin"]
    )
    def get(self, request: Request, course_slug: str) -> Response:
        """Return the draft/published pair, seeding a fresh draft from
        the default design when the course never had one."""
        template = template_service.get_template(course_slug=course_slug)
        return Response(
            TemplateDetailSerializer(template).data, status=status.HTTP_200_OK
        )

    @extend_schema(
        request=TemplateDraftSerializer,
        responses={200: TemplateDetailSerializer},
        tags=["certificates-admin"],
    )
    def put(self, request: Request, course_slug: str) -> Response:
        """Replace the draft — the designer's debounced autosave."""
        serializer = TemplateDraftSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        template = template_service.save_draft(
            course_slug=course_slug,
            design=serializer.validated_data["design"],
            actor_id=request.user.id,
        )
        return Response(
            TemplateDetailSerializer(template).data, status=status.HTTP_200_OK
        )

    @extend_schema(responses={204: None}, tags=["certificates-admin"])
    def delete(self, request: Request, course_slug: str) -> Response:
        """Drop the row — the course returns to the built-in default."""
        template_service.remove_template(
            course_slug=course_slug, actor_id=request.user.id
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminTemplatePublishView(ServiceAPIView):
    """The deliberate act: draft becomes the production design."""

    permission_classes = (IsAdminUser,)

    @extend_schema(
        request=None,
        responses={200: TemplateDetailSerializer},
        tags=["certificates-admin"],
    )
    def post(self, request: Request, course_slug: str) -> Response:
        """Publish the current draft."""
        template = template_service.publish(
            course_slug=course_slug, actor_id=request.user.id
        )
        return Response(
            TemplateDetailSerializer(template).data, status=status.HTTP_200_OK
        )


class AdminTemplateResetView(ServiceAPIView):
    """Throw the experiment away: draft := published (or the default)."""

    permission_classes = (IsAdminUser,)

    @extend_schema(
        request=None,
        responses={200: TemplateDetailSerializer},
        tags=["certificates-admin"],
    )
    def post(self, request: Request, course_slug: str) -> Response:
        """Reset the draft to the last published version."""
        template = template_service.reset_draft(
            course_slug=course_slug, actor_id=request.user.id
        )
        return Response(
            TemplateDetailSerializer(template).data, status=status.HTTP_200_OK
        )
