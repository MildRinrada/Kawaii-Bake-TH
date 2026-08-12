"""Serializers for certificate and achievement payloads.

Read-only field maps, plus the one write shape: the name a first
certificate must be printed with.
"""

from __future__ import annotations

from rest_framework import serializers

from apps.certificates.constants import CertificateStatus
from apps.certificates.models import Certificate
from apps.common.api.serializers import StrictSerializer
from apps.users.constants import NAME_PART_MAX_LENGTH


class CertificateIssueSerializer(StrictSerializer):
    """Validates the optional body of an issuance request.

    Both parts are optional because an account that already carries a
    legal name needs no body at all; the service decides whether what
    arrived is enough and answers ``legal_name_required`` when it is not.
    ``last_name`` may be blank  a mononym is a real kind of name  but
    the two cannot both be empty, which is the service's rule since it
    also holds for what is already stored.
    """

    first_name = serializers.CharField(
        max_length=NAME_PART_MAX_LENGTH, required=False, allow_blank=True, default=""
    )
    last_name = serializers.CharField(
        max_length=NAME_PART_MAX_LENGTH, required=False, allow_blank=True, default=""
    )


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
