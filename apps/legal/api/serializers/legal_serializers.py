"""Serializers for the legal-document endpoints."""

from __future__ import annotations

from rest_framework import serializers

from apps.common.api.serializers import StrictSerializer
from apps.legal.constants import TITLE_MAX_LENGTH


class LegalDocumentSummarySerializer(serializers.Serializer):
    """List row: everything but the body, which can be long."""

    kind = serializers.CharField(read_only=True)
    title = serializers.CharField(read_only=True)
    version = serializers.IntegerField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)


class LegalDocumentSerializer(LegalDocumentSummarySerializer):
    """Detail: the summary plus the full text."""

    body = serializers.CharField(read_only=True)


class LegalDocumentUpdateSerializer(StrictSerializer):
    """Validates a staff edit. Absent means unchanged; blank is refused 
    an empty legal document is a bug, not a state."""

    title = serializers.CharField(max_length=TITLE_MAX_LENGTH, required=False)
    body = serializers.CharField(required=False)

    def validate(self, attrs: dict[str, object]) -> dict[str, object]:
        """Refuse a PATCH that changes nothing."""
        if not attrs:
            raise serializers.ValidationError(
                "Provide a new title and/or body."
            )
        return attrs
