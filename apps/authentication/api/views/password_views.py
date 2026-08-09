"""Password reset and password change endpoints."""

from __future__ import annotations

from django.contrib.auth import update_session_auth_hash
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.authentication.api.serializers import (
    PasswordChangeSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
)
from apps.authentication.services import password_reset_service
from apps.common.api.views import CsrfProtectedAPIView, ServiceAPIView


class PasswordResetRequestView(CsrfProtectedAPIView):
    """Request a password-reset link."""

    authentication_classes = ()
    permission_classes = (AllowAny,)

    @extend_schema(
        request=PasswordResetRequestSerializer,
        responses={202: None},
        tags=["auth"],
    )
    def post(self, request: Request) -> Response:
        """Send a reset link if the address is eligible.

        Always answers 202, whether or not an account exists. Reporting "no
        such account" here would turn the endpoint into an enumeration oracle.
        """
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        password_reset_service.request_password_reset(
            email=serializer.validated_data["email"]
        )
        return Response(status=status.HTTP_202_ACCEPTED)


class PasswordResetConfirmView(CsrfProtectedAPIView):
    """Complete a password reset from an emailed link."""

    authentication_classes = ()
    permission_classes = (AllowAny,)

    @extend_schema(
        request=PasswordResetConfirmSerializer,
        responses={200: None},
        tags=["auth"],
    )
    def post(self, request: Request) -> Response:
        """Validate the token and set the new password.

        Every existing session for the account is invalidated as a side effect,
        because changing the password rotates the session-auth hash.
        """
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        password_reset_service.confirm_password_reset(
            uidb64=serializer.validated_data["uid"],
            token=serializer.validated_data["token"],
            new_password=serializer.validated_data["new_password"],
        )
        return Response({"detail": "Password updated."}, status=status.HTTP_200_OK)


class PasswordChangeView(ServiceAPIView):
    """Change the signed-in user's password."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        request=PasswordChangeSerializer,
        responses={200: None},
        tags=["auth"],
    )
    def post(self, request: Request) -> Response:
        """Change the password and keep the caller signed in.

        ``update_session_auth_hash`` re-stamps *this* session so the user who
        made the change stays in, while every other session is invalidated.
        """
        serializer = PasswordChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = password_reset_service.change_password(
            user=request.user,
            current_password=serializer.validated_data["current_password"],
            new_password=serializer.validated_data["new_password"],
        )
        update_session_auth_hash(request._request, user)
        return Response({"detail": "Password updated."}, status=status.HTTP_200_OK)
