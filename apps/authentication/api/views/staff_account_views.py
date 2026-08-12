"""Staff-only account actions: create, reset link, verification resend.

Mounted under ``/api/v1/admin/users/`` alongside the roster (which lives
in ``apps.users``); these three live here because they mint credentials
and email flows. The ``admin/`` prefix is a naming convention, not the
permission: every view declares ``IsAdminUser`` itself (ADR 0022).
"""

from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAdminUser
from rest_framework.request import Request
from rest_framework.response import Response

from apps.authentication.api.serializers.staff_serializers import (
    AdminCreatedUserSerializer,
    AdminCreateUserSerializer,
    StaffActionResultSerializer,
)
from apps.authentication.services import staff_account_service
from apps.common.api.views import ServiceAPIView


class AdminCreateUserView(ServiceAPIView):
    """Create an account on a member's behalf."""

    permission_classes = (IsAdminUser,)

    @extend_schema(
        request=AdminCreateUserSerializer,
        responses={201: AdminCreatedUserSerializer},
        tags=["users-admin"],
    )
    def post(self, request: Request) -> Response:
        """Create the account; unverified ones get the verification email."""
        serializer = AdminCreateUserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = staff_account_service.admin_create_user(
            actor_id=request.user.id, **serializer.validated_data
        )
        return Response(
            AdminCreatedUserSerializer(user).data,
            status=status.HTTP_201_CREATED,
        )


class AdminSendPasswordResetView(ServiceAPIView):
    """Email a password-reset link to one account."""

    permission_classes = (IsAdminUser,)

    @extend_schema(
        request=None,
        responses={200: StaffActionResultSerializer},
        tags=["users-admin"],
    )
    def post(self, request: Request, user_id: int) -> Response:
        """Dispatch the reset email, or report ineligibility honestly."""
        staff_account_service.send_password_reset(
            actor_id=request.user.id, user_id=user_id
        )
        return Response({"sent": True})


class AdminResendVerificationView(ServiceAPIView):
    """Re-send the email-verification link to one account."""

    permission_classes = (IsAdminUser,)

    @extend_schema(
        request=None,
        responses={200: StaffActionResultSerializer},
        tags=["users-admin"],
    )
    def post(self, request: Request, user_id: int) -> Response:
        """Dispatch the verification email, or report ineligibility."""
        staff_account_service.resend_verification(
            actor_id=request.user.id, user_id=user_id
        )
        return Response({"sent": True})
