"""Serializers for the reward endpoints."""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.common.api.serializers import StrictSerializer
from apps.rewards.constants import (
    MAX_ADJUSTMENT_MAGNITUDE,
    NOTE_MAX_LENGTH,
    REASON_TEXT,
)


class RewardSummarySerializer(serializers.Serializer):
    """The caller's balance and lifetime totals."""

    balance = serializers.IntegerField(read_only=True)
    lifetime_earned = serializers.IntegerField(read_only=True)
    lifetime_spent = serializers.IntegerField(read_only=True)


class ReasonSerializer(serializers.Serializer):
    """A reason code with its bilingual presentation."""

    code = serializers.CharField(read_only=True)
    title_th = serializers.CharField(read_only=True)
    title_en = serializers.CharField(read_only=True)


class RewardTransactionSerializer(serializers.Serializer):
    """One immutable ledger entry.

    No internal ids and no event keys — the row is information, not an
    addressable resource; there is nothing a client could do to it.
    """

    kind = serializers.CharField(read_only=True)
    amount = serializers.IntegerField(read_only=True)
    balance_after = serializers.IntegerField(read_only=True)
    reason = serializers.SerializerMethodField()
    note = serializers.CharField(read_only=True)
    actor_handle = serializers.CharField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)

    def get_reason(self, obj: Any) -> dict[str, str]:
        """Return the bilingual presentation of the reason code."""
        text = REASON_TEXT[obj.reason_code]
        return {"code": obj.reason_code, "title_th": text.th, "title_en": text.en}


class TransactionListQuerySerializer(StrictSerializer):
    """Validates the query string of the history endpoint."""

    page = serializers.IntegerField(required=False, min_value=1)
    page_size = serializers.IntegerField(required=False, min_value=1)


class ClaimResultSerializer(serializers.Serializer):
    """The outcome of one claim call."""

    claimed = serializers.IntegerField(read_only=True)
    points = serializers.IntegerField(read_only=True)
    balance = serializers.IntegerField(read_only=True)


class AdjustmentSerializer(StrictSerializer):
    """Validates a staff balance adjustment."""

    username = serializers.CharField(max_length=150)
    amount = serializers.IntegerField(
        min_value=-MAX_ADJUSTMENT_MAGNITUDE, max_value=MAX_ADJUSTMENT_MAGNITUDE
    )
    reason = serializers.CharField(max_length=NOTE_MAX_LENGTH)
    idempotency_key = serializers.CharField(required=False, max_length=64)
