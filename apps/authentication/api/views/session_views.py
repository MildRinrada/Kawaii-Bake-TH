"""Sign-in, sign-out, session bootstrap and registration endpoints."""

from __future__ import annotations

from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.authentication.api.credentials import get_credential_issuer
from apps.authentication.api.serializers import (
    AuthenticatedResponseSerializer,
    LoginSerializer,
    RegistrationSerializer,
    UsernameAvailabilityQuerySerializer,
    UsernameAvailabilityResponseSerializer,
)
from apps.authentication.services import login_service, registration_service
from apps.common.api.views import CsrfProtectedAPIView, ServiceAPIView, client_ip
from apps.users.api.serializers import MeSerializer
from apps.users.selectors import user_selector


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfView(ServiceAPIView):
    """Issue the CSRF cookie the frontend must echo on unsafe requests."""

    authentication_classes = ()
    permission_classes = (AllowAny,)

    @extend_schema(responses={204: None}, tags=["auth"])
    def get(self, request: Request) -> Response:
        """Set the ``csrftoken`` cookie and return no content."""
        return Response(status=status.HTTP_204_NO_CONTENT)


class RegistrationView(CsrfProtectedAPIView):
    """Create a new account."""

    authentication_classes = ()
    permission_classes = (AllowAny,)

    @extend_schema(
        request=RegistrationSerializer,
        responses={201: MeSerializer},
        tags=["auth"],
    )
    def post(self, request: Request) -> Response:
        """Register an account and dispatch its verification email.

        Registration does not sign the user in: establishing a session is a
        separate concern, and keeping it out of this path means the flow works
        identically once JWT replaces cookies.
        """
        serializer = RegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = registration_service.register_user(
            email=serializer.validated_data["email"],
            username=serializer.validated_data["username"],
            password=serializer.validated_data["password"],
            client_ip=client_ip(request),
        )
        payload = user_selector.get_me(user_id=user.pk)
        return Response(
            MeSerializer(payload, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )


class UsernameAvailabilityView(ServiceAPIView):
    """Live availability check for the sign-up form's handle field."""

    authentication_classes = ()
    permission_classes = (AllowAny,)

    @extend_schema(
        parameters=[UsernameAvailabilityQuerySerializer],
        responses={200: UsernameAvailabilityResponseSerializer},
        tags=["auth"],
    )
    def get(self, request: Request) -> Response:
        """Report whether ``?username=`` could be registered right now.

        Advisory only — the racing-sign-up case is still settled by the
        unique constraint inside registration.
        """
        serializer = UsernameAvailabilityQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        username = serializer.validated_data["username"]
        available = registration_service.is_username_available(
            username=username, client_ip=client_ip(request)
        )
        return Response(
            {"username": username.strip().lower(), "available": available},
            status=status.HTTP_200_OK,
        )


class LoginView(CsrfProtectedAPIView):
    """Authenticate and start a session."""

    authentication_classes = ()
    permission_classes = (AllowAny,)

    @extend_schema(
        request=LoginSerializer,
        responses={200: AuthenticatedResponseSerializer},
        tags=["auth"],
    )
    def post(self, request: Request) -> Response:
        """Verify credentials, then issue a credential for the client."""
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = login_service.authenticate_user(
            email=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
            client_ip=client_ip(request),
        )

        issuer = get_credential_issuer()
        credential = issuer.issue(
            request=request._request,
            user=user,
            remember=serializer.validated_data["remember_me"],
        )

        payload = user_selector.get_me(user_id=user.pk)
        response = Response(
            {
                "status": credential.status,
                "user": MeSerializer(
                    payload, context=self.get_serializer_context()
                ).data,
                **credential.body,
            },
            status=status.HTTP_200_OK,
        )
        issuer.apply(response=response, credential=credential)
        return response


class LogoutView(ServiceAPIView):
    """End the caller's session."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(request=None, responses={204: None}, tags=["auth"])
    def post(self, request: Request) -> Response:
        """Revoke the caller's credential.

        POST-only: Django 5 removed GET logout precisely because a prefetching
        browser or an ``<img>`` tag could trigger it.
        """
        get_credential_issuer().revoke(request=request._request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(ServiceAPIView):
    """Return the current authentication state."""

    permission_classes = (AllowAny,)

    @extend_schema(responses={200: MeSerializer}, tags=["auth"])
    def get(self, request: Request) -> Response:
        """Return the signed-in user, or ``{"user": null}`` when anonymous.

        Anonymous is answered with 200 rather than 401 on purpose: the frontend
        calls this on every page load, and "nobody is signed in" is a normal
        state, not an error for clients and error trackers to special-case.
        """
        if not request.user.is_authenticated:
            return Response({"user": None}, status=status.HTTP_200_OK)

        payload = user_selector.get_me(user_id=request.user.id)
        return Response(
            {"user": MeSerializer(payload, context=self.get_serializer_context()).data},
            status=status.HTTP_200_OK,
        )
