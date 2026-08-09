"""Profile endpoints.

Views parse the request into primitives, call a service, and serialise the
result. No business logic and no ORM access lives here.
"""

from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.common.api.views import ServiceAPIView
from apps.users.api.serializers import (
    OwnProfileSerializer,
    ProfileUpdateSerializer,
    PublicProfileSerializer,
)
from apps.users.services import profile_service


class ProfileDetailView(ServiceAPIView):
    """Return the signed-in user's own profile."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(responses=OwnProfileSerializer, tags=["users"])
    def get(self, request: Request) -> Response:
        """Return the caller's profile."""
        profile = profile_service.get_own_profile(user_id=request.user.id)
        serializer = OwnProfileSerializer(profile, context=self.get_serializer_context())
        return Response(serializer.data, status=status.HTTP_200_OK)


class ProfileUpdateView(ServiceAPIView):
    """Partially update the signed-in user's profile."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        request=ProfileUpdateSerializer,
        responses=OwnProfileSerializer,
        tags=["users"],
    )
    def patch(self, request: Request) -> Response:
        """Validate and apply profile changes.

        Only the keys present in the payload are changed; an explicit ``null``
        on a nullable field clears it.
        """
        serializer = ProfileUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        profile = profile_service.update_profile(
            user_id=request.user.id, changes=serializer.validated_data
        )
        return Response(
            OwnProfileSerializer(profile, context=self.get_serializer_context()).data,
            status=status.HTTP_200_OK,
        )


class PublicProfileView(ServiceAPIView):
    """Return another user's profile, redacted by their privacy settings."""

    permission_classes = (AllowAny,)

    @extend_schema(responses=PublicProfileSerializer, tags=["users"])
    def get(self, request: Request, username: str) -> Response:
        """Return the requested public profile.

        A profile that does not exist and one the viewer may not see are both
        reported as 404, so the endpoint cannot be used to enumerate accounts.
        """
        viewer = request.user
        viewer_id = viewer.id if viewer.is_authenticated else None

        profile = profile_service.get_public_profile(
            username=username,
            viewer_id=viewer_id,
            viewer_is_staff=bool(viewer.is_authenticated and viewer.is_staff),
        )
        serializer = PublicProfileSerializer(
            profile, context=self.get_serializer_context()
        )
        return Response(serializer.data, status=status.HTTP_200_OK)
