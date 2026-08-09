"""Recipe category endpoints."""

from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from apps.common.api.views import ServiceAPIView
from apps.recipe_categories.api.serializers import CategorySerializer
from apps.recipe_categories.services import category_service


class CategoryListView(ServiceAPIView):
    """List the active recipe categories."""

    permission_classes = (AllowAny,)

    @extend_schema(responses={200: CategorySerializer(many=True)}, tags=["recipe-categories"])
    def get(self, request: Request) -> Response:
        """Return every active category with its published recipe count.

        Deliberately unpaginated: the taxonomy is a small, curated set that the
        frontend loads once to build filter controls.
        """
        categories = category_service.list_active_categories()
        return Response(
            CategorySerializer(categories, many=True).data, status=status.HTTP_200_OK
        )
