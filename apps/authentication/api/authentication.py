"""DRF authentication class for cookie sessions."""

from __future__ import annotations

from typing import Any

from rest_framework.authentication import SessionAuthentication


class CsrfEnforcedSessionAuthentication(SessionAuthentication):
    """Session authentication that always enforces CSRF.

    ``SessionAuthentication`` already calls ``enforce_csrf`` for authenticated
    requests. This subclass exists to name that guarantee explicitly and to give
    a single place to adjust it.

    Note the complementary hole it does **not** cover: DRF wraps every
    ``APIView`` in ``csrf_exempt``, and this class only runs once a session
    cookie is present. Unauthenticated POST endpoints (login, register, reset)
    are therefore protected by
    :class:`~apps.common.api.views.CsrfProtectedAPIView` instead.
    """

    def authenticate_header(self, request: Any) -> str:
        """Return a ``WWW-Authenticate`` value.

        The base class returns ``None``, which makes DRF answer unauthenticated
        requests with 403. The shared exception handler normalises that to 401;
        returning a header here keeps the response self-describing.
        """
        return "Session"
