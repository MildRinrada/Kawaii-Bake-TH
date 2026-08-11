"""Serializers for the staff achievements surface."""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.certificates.api.serializers.certificate_serializers import (
    BadgeSerializer,
)
from apps.certificates.constants import AchievementType
from apps.common.api.serializers import (
    PaginatedFilterSerializer,
    StrictSerializer,
)


class AdminBadgeSerializer(BadgeSerializer):
    """A badge on the staff surface - adds curation state and usage."""

    is_active = serializers.BooleanField(read_only=True)
    awarded_count = serializers.IntegerField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)


class BadgeCreateSerializer(StrictSerializer):
    """Payload for creating a badge definition."""

    slug = serializers.SlugField(max_length=50)
    title_th = serializers.CharField(max_length=100)
    title_en = serializers.CharField(max_length=100)
    description_th = serializers.CharField(
        max_length=255, required=False, allow_blank=True
    )
    description_en = serializers.CharField(
        max_length=255, required=False, allow_blank=True
    )
    icon = serializers.CharField(max_length=50, required=False, allow_blank=True)
    is_active = serializers.BooleanField(required=False)


class BadgeUpdateSerializer(StrictSerializer):
    """Payload for editing a badge; absent keys are unchanged."""

    slug = serializers.SlugField(max_length=50, required=False)
    title_th = serializers.CharField(max_length=100, required=False)
    title_en = serializers.CharField(max_length=100, required=False)
    description_th = serializers.CharField(
        max_length=255, required=False, allow_blank=True
    )
    description_en = serializers.CharField(
        max_length=255, required=False, allow_blank=True
    )
    icon = serializers.CharField(max_length=50, required=False, allow_blank=True)
    is_active = serializers.BooleanField(required=False)


class AdminAwardSerializer(serializers.Serializer):
    """One row of the cross-user award ledger."""

    id = serializers.IntegerField(read_only=True)
    username = serializers.CharField(read_only=True, source="user.username")
    display_name = serializers.SerializerMethodField()
    achievement_type = serializers.CharField(read_only=True)
    badge = BadgeSerializer(read_only=True, allow_null=True)
    awarded_at = serializers.DateTimeField(read_only=True)

    def get_display_name(self, obj: Any) -> str:
        """Return the earner's display name, falling back to the handle."""
        profile = getattr(obj.user, "profile", None)
        return (profile.display_name if profile else "") or obj.user.username


class AwardFilterSerializer(PaginatedFilterSerializer):
    """Query parameters accepted by the award ledger."""

    search = serializers.CharField(
        max_length=120, required=False, allow_blank=True
    )
    achievement_type = serializers.ChoiceField(
        choices=AchievementType.choices, required=False, allow_blank=True
    )


class AdminCertificateSerializer(serializers.Serializer):
    """One row of the platform-wide certificate registry.

    Carries the holder's handle and the revocation attribution - data
    only the ``IsAdminUser``-gated registry may show. The public
    verification shape stays as narrow as ever.
    """

    id = serializers.IntegerField(read_only=True)
    certificate_number = serializers.CharField(read_only=True)
    verification_token = serializers.UUIDField(read_only=True)
    username = serializers.CharField(read_only=True, source="user.username")
    display_name = serializers.SerializerMethodField()
    student_name = serializers.CharField(read_only=True)
    course_title = serializers.CharField(read_only=True)
    completed_at = serializers.DateTimeField(read_only=True)
    issued_at = serializers.DateTimeField(read_only=True)
    status = serializers.SerializerMethodField()
    revoked_at = serializers.DateTimeField(read_only=True, allow_null=True)
    revoked_by = serializers.SerializerMethodField()
    revoked_reason = serializers.CharField(read_only=True)

    def get_display_name(self, obj: Any) -> str:
        """Return the holder's display name, falling back to the handle."""
        profile = getattr(obj.user, "profile", None)
        return (profile.display_name if profile else "") or obj.user.username

    def get_status(self, obj: Any) -> str:
        """Return ``valid`` or ``revoked``."""
        return "revoked" if obj.revoked_at else "valid"

    def get_revoked_by(self, obj: Any) -> str | None:
        """Return the revoking operator's handle, when recorded."""
        return obj.revoked_by.username if obj.revoked_by else None


class CertificateFilterSerializer(PaginatedFilterSerializer):
    """Query parameters accepted by the certificate registry."""

    search = serializers.CharField(
        max_length=120, required=False, allow_blank=True
    )
    username = serializers.CharField(
        max_length=150, required=False, allow_blank=True
    )
    status = serializers.ChoiceField(
        choices=("valid", "revoked"), required=False, allow_blank=True
    )


class CertificateRevokeSerializer(StrictSerializer):
    """Payload for a staff revocation - the reason is not optional."""

    reason = serializers.CharField(max_length=200)
