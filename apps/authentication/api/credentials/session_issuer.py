"""Session-cookie credential issuer (Phase 1)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from django.contrib.auth import login as django_login
from django.contrib.auth import logout as django_logout

from apps.authentication.api.credentials.base import IssuedCredential
from apps.authentication.constants import (
    REMEMBER_ME_SECONDS,
    SESSION_EXPIRE_ON_BROWSER_CLOSE,
)
from apps.authentication.exceptions import CredentialRefreshNotSupportedError

if TYPE_CHECKING:  # pragma: no cover - typing only
    from django.http import HttpRequest
    from rest_framework.response import Response

    from apps.users.models import User

BACKEND_PATH = "apps.authentication.auth_backends.email_backend.EmailBackend"


class SessionCredentialIssuer:
    """Issues httpOnly session cookies.

    Chosen for Phase 1 because it gives real server-side revocation, adds no
    tables, and keeps the credential unreadable to JavaScript. See
    ``docs/adr/0007-session-auth-for-phase-1.md``.

    This is the only module in the project permitted to call
    ``django.contrib.auth.login`` or ``logout``.
    """

    def issue(
        self, *, request: HttpRequest, user: User, remember: bool
    ) -> IssuedCredential:
        """Start an authenticated session.

        Args:
            request: The current request; its session is rotated.
            user: The already-authenticated user.
            remember: Whether the session should outlive the browser session.

        Returns:
            An empty credential  the cookie is set by ``SessionMiddleware``.
        """
        # `backend=` is passed explicitly so that appending an OAuth backend
        # later cannot raise "multiple authentication backends configured".
        # `login()` cycles the session key, which defeats session fixation.
        django_login(request, user, backend=BACKEND_PATH)

        # Must run *after* login(): login() may flush the session when a
        # different user was previously signed in.
        request.session.set_expiry(
            REMEMBER_ME_SECONDS if remember else SESSION_EXPIRE_ON_BROWSER_CLOSE
        )
        return IssuedCredential()

    def revoke(self, *, request: HttpRequest) -> None:
        """End the caller's session, deleting the server-side record.

        Args:
            request: The current request.
        """
        django_logout(request)

    def refresh(
        self, *, request: HttpRequest, payload: Mapping[str, Any]
    ) -> IssuedCredential:
        """Not applicable to sessions.

        The session engine extends sessions on its own schedule, so there is
        nothing to exchange. The endpoint exists only so the JWT contract is
        already routed.

        Raises:
            CredentialRefreshNotSupportedError: Always.
        """
        raise CredentialRefreshNotSupportedError

    def apply(self, *, response: Response, credential: IssuedCredential) -> None:
        """No-op: ``SessionMiddleware`` writes the cookie."""
        return None
