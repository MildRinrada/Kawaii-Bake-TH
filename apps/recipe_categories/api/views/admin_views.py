"""Staff-only category curation endpoints.

The ``admin/`` URL prefix is a naming convention, not the permission:
every view here declares ``IsAdminUser`` itself (ADR 0022), so a future
re-mount cannot accidentally expose them.
"""

from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAdminUser
from rest_framework.request import Request
from rest_framework.response import Response

from apps.common.api.views import ServiceAPIView
from apps.recipe_categories.api.serializers import (
    AdminCategorySerializer,
    CategoryCreateSerializer,
    CategoryUpdateSerializer,
)
from apps.recipe_categories.services import category_service


class AdminCategoryListView(ServiceAPIView):
    """List every category and create new ones."""

    permission_classes = (IsAdminUser,)
    # Multipart for the image upload, JSON for plain edits (including the
    # explicit ``image: null`` removal, which multipart cannot express).
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    @extend_schema(
        responses={200: AdminCategorySerializer(many=True)},
        tags=["recipe-categories-admin"],
    )
    def get(self, request: Request) -> Response:
        """Return every category, inactive included.

        Unpaginated for the same reason as the public list: the taxonomy is
        a small, curated set the admin screen loads once.
        """
        categories = category_service.list_all_categories()
        return Response(
            AdminCategorySerializer(
                categories, many=True, context=self.get_serializer_context()
            ).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        request=CategoryCreateSerializer,
        responses={201: AdminCategorySerializer},
        tags=["recipe-categories-admin"],
    )
    def post(self, request: Request) -> Response:
        """Create a category; the slug derives from the name when omitted."""
        serializer = CategoryCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = dict(serializer.validated_data)
        category = category_service.create_category(
            actor_id=request.user.id,
            name=values.pop("name"),
            slug=values.pop("slug", ""),
            **values,
        )
        return Response(
            AdminCategorySerializer(
                category, context=self.get_serializer_context()
            ).data,
            status=status.HTTP_201_CREATED,
        )


class AdminCategoryDetailView(ServiceAPIView):
    """Edit or delete one category."""

    permission_classes = (IsAdminUser,)
    # Multipart for the image upload, JSON for plain edits (including the
    # explicit ``image: null`` removal, which multipart cannot express).
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    @extend_schema(
        request=CategoryUpdateSerializer,
        responses={200: AdminCategorySerializer},
        tags=["recipe-categories-admin"],
    )
    def patch(self, request: Request, category_id: int) -> Response:
        """Apply a partial edit; ``image: null`` removes the tile photo."""
        serializer = CategoryUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        category = category_service.update_category(
            actor_id=request.user.id,
            category_id=category_id,
            changes=serializer.validated_data,
        )
        return Response(
            AdminCategorySerializer(
                category, context=self.get_serializer_context()
            ).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(responses={204: None}, tags=["recipe-categories-admin"])
    def delete(self, request: Request, category_id: int) -> Response:
        """Delete the category; recipe/course assignments simply unlink."""
        category_service.delete_category(
            actor_id=request.user.id, category_id=category_id
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
