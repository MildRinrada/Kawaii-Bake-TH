"""Serializers for certificate and achievement payloads.

All read-only field maps  issuance takes no body, and nothing here is
ever written through a serializer.
"""

from __future__ import annotations

from rest_framework import serializers

from apps.certificates.constants import CertificateStatus
from apps.certificates.models import Certificate


class CertificateSerializer(serializers.Serializer):
    """The owner's view of a certificate  the printable metadata."""

    id = serializers.IntegerField(read_only=True)
    certificate_number = serializers.CharField(read_only=True)
    verification_token = serializers.UUIDField(read_only=True)
    course_id = serializers.IntegerField(read_only=True, allow_null=True)
    course_title = serializers.CharField(read_only=True)
    student_name = serializers.CharField(read_only=True)
    completed_at = serializers.DateTimeField(read_only=True)
    issued_at = serializers.DateTimeField(read_only=True)
    status = serializers.SerializerMethodField()

    def get_status(self, obj: Certificate) -> str:
        """Return ``valid`` or ``revoked``."""
        return (
            CertificateStatus.REVOKED if obj.is_revoked else CertificateStatus.VALID
        )


class CertificateVerificationSerializer(serializers.Serializer):
    """The public (employer-facing) view  deliberately narrow.

    The student's public handle as printed, the course, the dates, the
    verdict. Never an email, never a user id, never the internal pk.
    """

    certificate_number = serializers.CharField(read_only=True)
    course_title = serializers.CharField(read_only=True)
    student_name = serializers.CharField(read_only=True)
    issued_at = serializers.DateTimeField(read_only=True)
    status = serializers.SerializerMethodField()

    def get_status(self, obj: Certificate) -> str:
        """Return ``valid`` or ``revoked``."""
        return (
            CertificateStatus.REVOKED if obj.is_revoked else CertificateStatus.VALID
        )


class BadgeSerializer(serializers.Serializer):
    """Display metadata for one badge.

    The same shape whether it is embedded in an earned achievement or
    listed in the catalogue: presentation only, no user data, nothing
    about whether *this* caller earned it  that fact lives on the
    achievement row (ADR 0024).
    """

    slug = serializers.CharField(read_only=True)
    title_th = serializers.CharField(read_only=True)
    title_en = serializers.CharField(read_only=True)
    description_th = serializers.CharField(read_only=True)
    description_en = serializers.CharField(read_only=True)
    icon = serializers.CharField(read_only=True)


# The embedded name kept for the achievement payload's existing shape.
_BadgeSerializer = BadgeSerializer


class AchievementSerializer(serializers.Serializer):
    """One earned achievement with its badge presentation."""

    id = serializers.IntegerField(read_only=True)
    achievement_type = serializers.CharField(read_only=True)
    awarded_at = serializers.DateTimeField(read_only=True)
    metadata = serializers.JSONField(read_only=True)
    badge = _BadgeSerializer(read_only=True, allow_null=True)
