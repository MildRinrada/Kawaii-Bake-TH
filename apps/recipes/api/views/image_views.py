"""Recipe gallery image endpoints.

Gallery images get their own routes because nested file arrays inside
``multipart/form-data`` are impractical: the JSON body carries the recipe and
its nested arrays, while images are uploaded one at a time here.
"""

from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.common.api.views import ServiceAPIView
from apps.recipes.api.serializers import (
    RecipeImageSerializer,
    RecipeImageUploadSerializer,
)
from apps.recipes.services import image_service


class RecipeImageCreateView(ServiceAPIView):
    """Upload a gallery image."""

    permission_classes = (IsAuthenticated,)
    parser_classes = (MultiPartParser, FormParser)

    @extend_schema(
        request=RecipeImageUploadSerializer,
        responses={201: RecipeImageSerializer},
        tags=["recipes"],
    )
    def post(self, request: Request, slug: str) -> Response:
        """Attach an image to the recipe's gallery."""
        serializer = RecipeImageUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        image = image_service.add_gallery_image(
            slug=slug,
            viewer_id=request.user.id,
            viewer_is_staff=request.user.is_staff,
            image=serializer.validated_data["image"],
            caption=serializer.validated_data.get("caption", ""),
        )
        return Response(
            RecipeImageSerializer(image, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )


class RecipeImageDeleteView(ServiceAPIView):
    """Delete a gallery image."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(responses={204: None}, tags=["recipes"])
    def delete(self, request: Request, slug: str, image_id: int) -> Response:
        """Remove one gallery image and its stored file."""
        image_service.remove_gallery_image(
            slug=slug,
            image_id=image_id,
            viewer_id=request.user.id,
            viewer_is_staff=request.user.is_staff,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
