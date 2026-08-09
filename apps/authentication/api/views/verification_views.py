"""Email verification endpoints."""

from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.authentication.api.serializers import EmailVerificationConfirmSerializer
from apps.authentication.services import email_verification_service
from apps.common.api.views import CsrfProtectedAPIView, ServiceAPIView


class EmailVerificationConfirmView(CsrfProtectedAPIView):
    """Confirm an email address from an emailed link."""

    authentication_classes = ()
    permission_classes = (AllowAny,)

    @extend_schema(
        request=EmailVerificationConfirmSerializer,
        responses={200: None},
        tags=["auth"],
    )
    def post(self, request: Request) -> Response:
        """Validate the token and mark the address confirmed.

        Confirming does **not** sign the user in: a forwarded or leaked email
        would otherwise be an account-takeover vector.
        """
        serializer = EmailVerificationConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email_verification_service.confirm_email(
            uidb64=serializer.validated_data["uid"],
            token=serializer.validated_data["token"],
        )
        return Response({"detail": "Email confirmed."}, status=status.HTTP_200_OK)


class EmailVerificationResendView(ServiceAPIView):
    """Request a fresh confirmation email."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(request=None, responses={202: None}, tags=["auth"])
    def post(self, request: Request) -> Response:
        """Send a new confirmation link to the signed-in user."""
        email_verification_service.resend_verification_email(user=request.user)
        return Response(status=status.HTTP_202_ACCEPTED)
