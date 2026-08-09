"""Recipe search endpoint."""

from __future__ import annotations

from dataclasses import replace

from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from apps.common.api.views import PaginatedServiceAPIView
from apps.recipes.api.serializers import (
    RecipeListItemSerializer,
    RecipeSearchQuerySerializer,
)
from apps.recipes.api.views.recipe_views import build_filters
from apps.recipes.constants import Ordering, RecipeScope
from apps.recipes.selectors import recipe_selector


class RecipeSearchView(PaginatedServiceAPIView):
    """Search recipes by title and summary."""

    permission_classes = (AllowAny,)

    @extend_schema(
        parameters=[RecipeSearchQuerySerializer],
        responses={200: RecipeListItemSerializer(many=True)},
        tags=["recipes"],
    )
    def get(self, request: Request) -> Response:
        """Return a page of recipes matching ``q``.

        This is a separate view rather than an alias for the list endpoint
        because ``q`` is required and ordering defaults to relevance.

        It uses the **list** visibility rule, never the detail one: searching
        must not surface unlisted recipes, since being absent from discovery is
        the whole purpose of unlisted.
        """
        query = RecipeSearchQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)

        filters = build_filters(query.validated_data)
        filters = replace(
            filters,
            search=query.validated_data["q"],
            ordering=query.validated_data.get("ordering", Ordering.RELEVANCE),
            # Search always operates on the public set; `scope=mine` browsing
            # belongs to the list endpoint.
            scope=RecipeScope.PUBLIC,
        )

        queryset = recipe_selector.list_recipes(
            filters=filters,
            viewer_id=request.user.id if request.user.is_authenticated else None,
            viewer_is_staff=bool(
                request.user.is_authenticated and request.user.is_staff
            ),
        )
        return self.paginated_response(queryset, RecipeListItemSerializer)
