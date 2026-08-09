"""Serializers for gamification payloads — all read-only field maps."""

from __future__ import annotations

from rest_framework import serializers

from apps.gamification.models import UserLevel


class XPTransactionSerializer(serializers.Serializer):
    """One ledger entry."""

    id = serializers.IntegerField(read_only=True)
    reason = serializers.CharField(read_only=True)
    points = serializers.IntegerField(read_only=True)
    metadata = serializers.JSONField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)


class StreakSerializer(serializers.Serializer):
    """The caller's streak standing."""

    current = serializers.IntegerField(read_only=True, source="current_streak")
    longest = serializers.IntegerField(read_only=True, source="longest_streak")
    last_activity = serializers.DateField(
        read_only=True, source="last_activity_date", allow_null=True
    )


class _LevelSerializer(serializers.Serializer):
    """The caller's level standing."""

    current_level = serializers.IntegerField(read_only=True)
    current_xp = serializers.IntegerField(read_only=True)
    total_xp = serializers.IntegerField(read_only=True)


class GamificationSummarySerializer(serializers.Serializer):
    """The `/me/gamification/` payload (docs shape; assembled by the view)."""

    level = _LevelSerializer(read_only=True)
    streak = StreakSerializer(read_only=True)
    recent_transactions = XPTransactionSerializer(many=True, read_only=True)


class LeaderboardEntrySerializer(serializers.Serializer):
    """One public leaderboard row — handle, level, XP. Nothing else.

    The public handle is the identity users chose to be public; email and
    ids never appear here.
    """

    public_handle = serializers.SerializerMethodField()
    level = serializers.IntegerField(read_only=True, source="current_level")
    total_xp = serializers.IntegerField(read_only=True)

    def get_public_handle(self, obj: UserLevel) -> str:
        """Return the row holder's public handle."""
        return obj.user.username
