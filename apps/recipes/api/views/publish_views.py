"""Recipe lifecycle endpoints.

Status transitions have their own routes rather than riding on the generic
PATCH, so the completeness checks cannot be reached around.
"""

from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.common.api.views import ServiceAPIView
from apps.recipes.api.serializers import RecipeDetailSerializer
from apps.recipes.services import publish_service, recipe_service


class _TransitionView(ServiceAPIView):
    """Shared plumbing for the three lifecycle transitions."""

    permission_classes = (IsAuthenticated,)
    transition = ""

    def post(self, request: Request, slug: str) -> Response:
        """Apply the transition and return the updated recipe."""
        action = getattr(publish_service, self.transition)
        action(
            slug=slug, viewer_id=request.user.id, viewer_is_staff=request.user.is_staff
        )

        # Re-read through the detail selector so the response has the same
        # shape as a subsequent GET.
        recipe = recipe_service.get_recipe(
            slug=slug, viewer_id=request.user.id, viewer_is_staff=request.user.is_staff
        )
        return Response(
            RecipeDetailSerializer(recipe, context=self.get_serializer_context()).data,
            status=status.HTTP_200_OK,
        )


class RecipePublishView(_TransitionView):
    """Publish a recipe."""

    transition = "publish"

    @extend_schema(
        request=None, responses={200: RecipeDetailSerializer}, tags=["recipes"]
    )
    def post(self, request: Request, slug: str) -> Response:
        """Publish the recipe.

        Idempotent. Returns 400 ``recipe_not_publishable`` with **every**
        unmet requirement in ``details``, so the frontend can render a
        checklist instead of surfacing one problem per attempt.
        """
        return super().post(request, slug)


class RecipeUnpublishView(_TransitionView):
    """Return a recipe to draft."""

    transition = "unpublish"

    @extend_schema(
        request=None, responses={200: RecipeDetailSerializer}, tags=["recipes"]
    )
    def post(self, request: Request, slug: str) -> Response:
        """Unpublish the recipe, retaining its original publication date."""
        return super().post(request, slug)


class RecipeArchiveView(_TransitionView):
    """Archive a recipe."""

    transition = "archive"

    @extend_schema(
        request=None, responses={200: RecipeDetailSerializer}, tags=["recipes"]
    )
    def post(self, request: Request, slug: str) -> Response:
        """Archive the recipe. Reversible; unlike DELETE, nothing is lost."""
        return super().post(request, slug)
