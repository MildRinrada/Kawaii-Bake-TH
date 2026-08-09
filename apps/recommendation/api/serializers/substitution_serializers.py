"""Serializers for the ingredient substitution endpoint."""

from __future__ import annotations

from rest_framework import serializers

from apps.common.api.serializers import StrictSerializer
from apps.recommendation.constants import INGREDIENT_QUERY_MAX_LENGTH


class SubstitutionOptionSerializer(serializers.Serializer):
    """One substitution candidate."""

    name = serializers.CharField(read_only=True)
    ratio = serializers.CharField(read_only=True)
    note = serializers.CharField(read_only=True)
    confidence = serializers.CharField(read_only=True)


class IngredientSubstitutionSerializer(serializers.Serializer):
    """One recipe ingredient with its substitution candidates."""

    ingredient = serializers.CharField(read_only=True)
    normalized = serializers.CharField(read_only=True)
    substitutions = SubstitutionOptionSerializer(many=True, read_only=True)


class SubstitutionQuerySerializer(StrictSerializer):
    """Validates the query string of the substitution endpoint."""

    ingredient = serializers.CharField(
        required=False, max_length=INGREDIENT_QUERY_MAX_LENGTH
    )
