"""Recipe list, create, detail, update and delete endpoints."""

from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import NotAuthenticated
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.common.api.views import PaginatedServiceAPIView, ServiceAPIView
from apps.recipes.api.serializers import (
    RecipeCreateSerializer,
    RecipeDetailSerializer,
    RecipeListItemSerializer,
    RecipeListQuerySerializer,
    RecipeUpdateSerializer,
)
from apps.recipes.constants import RecipeScope
from apps.recipes.selectors import recipe_selector
from apps.recipes.selectors.recipe_filters import RecipeListFilters
from apps.recipes.services import recipe_service


def build_filters(validated: dict) -> RecipeListFilters:
    """Translate validated query parameters into the selector's input contract.

    Args:
        validated: Output of a filter serializer.

    Returns:
        The frozen filter set.
    """
    return RecipeListFilters(
        search=validated.get("search", "") or "",
        category_slugs=tuple(validated.get("category", ()) or ()),
        difficulty=tuple(validated.get("difficulty", ()) or ()),
        author_username=validated.get("author", "") or "",
        ingredient=validated.get("ingredient", "") or "",
        max_total_minutes=validated.get("max_total_minutes"),
        ordering=validated.get("ordering", RecipeListFilters.ordering),
        scope=validated.get("scope", RecipeScope.PUBLIC),
        status=validated.get("status", "") or "",
        visibility=validated.get("visibility", "") or "",
    )


class RecipeListCreateView(PaginatedServiceAPIView):
    """List visible recipes, or create a new one."""

    permission_classes = (AllowAny,)

    def get_permissions(self):
        """Require authentication for creation only."""
        if self.request.method == "POST":
            return [IsAuthenticated()]
        return super().get_permissions()

    @extend_schema(
        parameters=[RecipeListQuerySerializer],
        responses={200: RecipeListItemSerializer(many=True)},
        tags=["recipes"],
    )
    def get(self, request: Request) -> Response:
        """Return a page of recipes visible to the caller."""
        query = RecipeListQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)

        filters = build_filters(query.validated_data)
        if filters.scope == RecipeScope.MINE and not request.user.is_authenticated:
            raise NotAuthenticated

        queryset = recipe_selector.list_recipes(
            filters=filters,
            viewer_id=request.user.id if request.user.is_authenticated else None,
            viewer_is_staff=bool(
                request.user.is_authenticated and request.user.is_staff
            ),
        )
        return self.paginated_response(queryset, RecipeListItemSerializer)

    @extend_schema(
        request=RecipeCreateSerializer,
        responses={201: RecipeDetailSerializer},
        tags=["recipes"],
    )
    def post(self, request: Request) -> Response:
        """Create a recipe as a draft."""
        serializer = RecipeCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        recipe = recipe_service.create_recipe(
            author_id=request.user.id, data=serializer.validated_data
        )
        return Response(
            RecipeDetailSerializer(
                recipe, context=self.get_serializer_context()
            ).data,
            status=status.HTTP_201_CREATED,
        )


class RecipeDetailView(ServiceAPIView):
    """Read, update or delete one recipe."""

    permission_classes = (AllowAny,)

    def get_permissions(self):
        """Require authentication for anything that writes."""
        if self.request.method in {"PATCH", "PUT", "DELETE"}:
            return [IsAuthenticated()]
        return super().get_permissions()

    @extend_schema(responses={200: RecipeDetailSerializer}, tags=["recipes"])
    def get(self, request: Request, slug: str) -> Response:
        """Return one recipe.

        A recipe that does not exist and one the caller may not see both return
        404, so the endpoint cannot be used to discover which slugs exist.
        """
        recipe = recipe_service.get_recipe(
            slug=slug,
            viewer_id=request.user.id if request.user.is_authenticated else None,
            viewer_is_staff=bool(
                request.user.is_authenticated and request.user.is_staff
            ),
        )
        return Response(
            RecipeDetailSerializer(recipe, context=self.get_serializer_context()).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        request=RecipeUpdateSerializer,
        responses={200: RecipeDetailSerializer},
        tags=["recipes"],
    )
    def patch(self, request: Request, slug: str) -> Response:
        """Partially update a recipe.

        Supplying ``ingredients`` or ``steps`` replaces that collection entirely.
        """
        serializer = RecipeUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        recipe = recipe_service.update_recipe(
            slug=slug,
            viewer_id=request.user.id,
            viewer_is_staff=request.user.is_staff,
            data=serializer.validated_data,
        )
        return Response(
            RecipeDetailSerializer(recipe, context=self.get_serializer_context()).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(responses={204: None}, tags=["recipes"])
    def delete(self, request: Request, slug: str) -> Response:
        """Permanently delete a recipe and its stored files.

        Archiving is the reversible alternative and has its own endpoint.
        """
        recipe_service.delete_recipe(
            slug=slug, viewer_id=request.user.id, viewer_is_staff=request.user.is_staff
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
