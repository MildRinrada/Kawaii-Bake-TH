"""The two endpoints an unauthenticated browser is allowed to touch.

Both are deliberately tiny. This is the only attack surface the security
app adds to the public API, so everything about it is bounded: the policy
is a read of four settings, and the ingest accepts four signal kinds,
rate-limited, with the source address taken from the connection rather
than the body.
"""

from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from apps.common.api.views import ServiceAPIView, client_ip
from apps.security import config
from apps.security.api.serializers import (
    ClientPolicySerializer,
    ClientSignalResultSerializer,
    ClientSignalSerializer,
    EdgeSignalSerializer,
)
from apps.security.services import threat_service


class ClientPolicyView(ServiceAPIView):
    """What this deployment asks the browser guard to do."""

    permission_classes = (AllowAny,)
    authentication_classes = ()

    @extend_schema(responses={200: ClientPolicySerializer}, tags=["security"])
    def get(self, request: Request) -> Response:
        """Return the env-configured guard mode.

        Read on every page load, so it must stay a settings read with no
        database access.
        """
        return Response(
            {
                "guard_mode": config.client_guard_mode(),
                "exempt_authenticated": config.guard_exempts_authenticated(),
                "report_signals": config.client_reports_enabled(),
            },
            status=status.HTTP_200_OK,
        )


class ClientSignalView(ServiceAPIView):
    """Accept one browser-reported observation.

    Unauthenticated on purpose: the visitors this watches are by
    definition not signed in. That makes rate limiting non-optional —
    without the scope below, this endpoint would be a free way to fill
    the events table.
    """

    permission_classes = (AllowAny,)
    authentication_classes = ()
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "security_signal"

    @extend_schema(
        request=ClientSignalSerializer,
        responses={201: ClientSignalResultSerializer},
        tags=["security"],
    )
    def post(self, request: Request) -> Response:
        """Record the signal and acknowledge, revealing nothing back."""
        serializer = ClientSignalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data

        event = threat_service.record_client_signal(
            kind=payload["kind"],
            ip=client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
            path=payload.get("path", ""),
            request_id=getattr(request, "request_id", ""),
            detail=payload.get("detail") or {},
        )
        return Response(
            {"recorded": event is not None}, status=status.HTTP_201_CREATED
        )


#: Header the frontend edge presents to prove it is ours.
EDGE_SECRET_HEADER = "HTTP_X_KB_EDGE_SECRET"


class EdgeSignalView(ServiceAPIView):
    """Accept a signal the Next.js origin observed on our behalf.

    The public site is served by Next.js, so a scan of
    ``https://kawaiibake.example/.env`` never touches Django. The edge
    catches those, 404s them itself, and forwards the observation here.

    This is the **only** endpoint that records an address other than the
    caller's own, which is exactly why it is behind a shared secret and
    is disabled (404) whenever that secret is unset.
    """

    permission_classes = (AllowAny,)
    authentication_classes = ()
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "security_signal"

    @extend_schema(
        request=EdgeSignalSerializer,
        responses={201: ClientSignalResultSerializer},
        tags=["security"],
    )
    def post(self, request: Request) -> Response:
        """Verify the secret, then record against the visitor's address."""
        serializer = EdgeSignalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data

        event = threat_service.record_edge_signal(
            secret=request.META.get(EDGE_SECRET_HEADER, ""),
            kind=payload["kind"],
            ip=payload["ip"],
            user_agent=payload.get("user_agent", ""),
            path=payload.get("path", ""),
            request_id=getattr(request, "request_id", ""),
            detail=payload.get("detail") or {},
        )
        return Response(
            {"recorded": event is not None}, status=status.HTTP_201_CREATED
        )
