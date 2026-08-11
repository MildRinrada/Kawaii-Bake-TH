"""Serializers for the staff recommendation-debug surface."""

from __future__ import annotations

from rest_framework import serializers

from apps.common.api.serializers import StrictSerializer


class PreviewRowSerializer(serializers.Serializer):
    """One ranked candidate with its score still attached.

    Staff-only by construction (ADR 0028): the public feed never carries
    a score. The row stays aggregate - a number and reason codes, never
    the target user's raw history.
    """

    rank = serializers.IntegerField(read_only=True)
    target_id = serializers.IntegerField(read_only=True)
    slug = serializers.CharField(read_only=True, allow_null=True)
    title = serializers.CharField(read_only=True, allow_null=True)
    score = serializers.FloatField(read_only=True)
    reasons = serializers.ListField(
        child=serializers.CharField(), read_only=True
    )
    primary_category = serializers.CharField(read_only=True, allow_blank=True)


class PreviewResultSerializer(serializers.Serializer):
    """The preview envelope: whose feed, which kind, the ranked rows."""

    username = serializers.CharField(read_only=True)
    kind = serializers.CharField(read_only=True)
    count = serializers.IntegerField(read_only=True)
    items = PreviewRowSerializer(many=True, read_only=True)


class PreviewFilterSerializer(StrictSerializer):
    """Query parameters accepted by the preview endpoint."""

    username = serializers.CharField(max_length=150)
    kind = serializers.ChoiceField(
        choices=("recipes", "courses"), required=False
    )


class EngineConfigSerializer(serializers.Serializer):
    """The engine's tunable weights, straight from constants.

    Read-only: weights are code, not configuration - changing one is a
    deploy with tests, and this endpoint only makes the current values
    visible so the preview's numbers can be interpreted.
    """

    candidate_pool_size = serializers.IntegerField(read_only=True)
    positive_review_min_rating = serializers.IntegerField(read_only=True)
    w_category_match = serializers.FloatField(read_only=True)
    category_score_cap = serializers.FloatField(read_only=True)
    w_author_affinity = serializers.FloatField(read_only=True)
    w_rating_average = serializers.FloatField(read_only=True)
    w_rating_count = serializers.FloatField(read_only=True)
    rating_count_cap = serializers.IntegerField(read_only=True)
    w_favorite_count = serializers.FloatField(read_only=True)
    favorite_count_cap = serializers.IntegerField(read_only=True)
    w_recency = serializers.FloatField(read_only=True)
    recency_window_days = serializers.IntegerField(read_only=True)
    w_difficulty_fit = serializers.FloatField(read_only=True)
    diversity_penalty = serializers.FloatField(read_only=True)
    highly_rated_min_average = serializers.FloatField(read_only=True)
    highly_rated_min_count = serializers.IntegerField(read_only=True)
    popular_min_favorites = serializers.IntegerField(read_only=True)
