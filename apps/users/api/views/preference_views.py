"""User preference endpoints."""

from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.common.api.views import ServiceAPIView
from apps.users.api.serializers import (
    UserPreferenceSerializer,
    UserPreferenceUpdateSerializer,
)
from apps.users.services import profile_service


class PreferenceView(ServiceAPIView):
    """Read and update the signed-in user's private settings."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(responses=UserPreferenceSerializer, tags=["users"])
    def get(self, request: Request) -> Response:
        """Return the caller's preferences."""
        preference = profile_service.get_own_preference(user_id=request.user.id)
        return Response(
            UserPreferenceSerializer(preference).data, status=status.HTTP_200_OK
        )

    @extend_schema(
        request=UserPreferenceUpdateSerializer,
        responses=UserPreferenceSerializer,
        tags=["users"],
    )
    def patch(self, request: Request) -> Response:
        """Validate and apply preference changes."""
        serializer = UserPreferenceUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        preference = profile_service.update_preference(
            user_id=request.user.id, changes=serializer.validated_data
        )
        return Response(
            UserPreferenceSerializer(preference).data, status=status.HTTP_200_OK
        )
