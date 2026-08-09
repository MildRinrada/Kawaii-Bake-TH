"""The per-recipe ingredient substitution endpoint."""

from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from apps.common.api.views import ServiceAPIView
from apps.recommendation.api.serializers import (
    IngredientSubstitutionSerializer,
    SubstitutionQuerySerializer,
)
from apps.recommendation.services import substitution_service


class RecipeSubstitutionsView(ServiceAPIView):
    """GET /recipes/{slug}/substitutions/ — substitution candidates.

    Public, governed by the recipes visibility rule: a hidden recipe is the
    same 404 as an absent one. Unpaginated on purpose — the result is
    bounded by the recipe's own ingredient count.
    """

    permission_classes = (AllowAny,)

    @extend_schema(
        parameters=[SubstitutionQuerySerializer],
        responses={200: IngredientSubstitutionSerializer(many=True)},
        tags=["recommendations"],
    )
    def get(self, request: Request, slug: str) -> Response:
        """Return substitution candidates for the recipe's ingredients."""
        query = SubstitutionQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)

        results = substitution_service.for_recipe(
            slug=slug,
            viewer_id=request.user.id if request.user.is_authenticated else None,
            viewer_is_staff=request.user.is_staff,
            ingredient=query.validated_data.get("ingredient", ""),
        )
        data = IngredientSubstitutionSerializer(
            results, many=True, context=self.get_serializer_context()
        ).data
        return Response({"results": data})
