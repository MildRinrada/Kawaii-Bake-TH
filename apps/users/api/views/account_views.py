"""Account lifecycle endpoints."""

from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.authentication.api.credentials import get_credential_issuer
from apps.common.api.views import ServiceAPIView
from apps.users.services import user_service


class AccountDeactivateView(ServiceAPIView):
    """Deactivate the signed-in user's account."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(request=None, responses={204: None}, tags=["users"])
    def post(self, request: Request) -> Response:
        """Deactivate the account and end the current session.

        Deactivation invalidates every other session implicitly, because the
        auth backend re-checks ``is_active`` on each session restore. The
        caller's own credential is revoked explicitly so the response does not
        leave them holding a live cookie.
        """
        user_service.deactivate_account(user_id=request.user.id)
        get_credential_issuer().revoke(request=request._request)
        return Response(status=status.HTTP_204_NO_CONTENT)
