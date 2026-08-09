"""Helpers shared across authentication flows."""

from __future__ import annotations

from django.conf import settings
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode


def encode_uid(user_id: int) -> str:
    """Encode a user primary key for inclusion in a link.

    Args:
        user_id: The user's primary key.

    Returns:
        The URL-safe base64 encoding of the key.
    """
    return urlsafe_base64_encode(force_bytes(user_id))


def decode_uid(uidb64: str) -> int | None:
    """Decode a user primary key from a link.

    Args:
        uidb64: The encoded identifier.

    Returns:
        The primary key, or ``None`` when the value is malformed.
    """
    try:
        return int(force_str(urlsafe_base64_decode(uidb64)))
    except (TypeError, ValueError, OverflowError, UnicodeDecodeError):
        return None


def build_frontend_url(*, path: str, uidb64: str, token: str) -> str:
    """Build a link that lands on the Next.js frontend, never on Django.

    Django renders no pages, so verification and reset links must point at the
    frontend, which reads the parameters and POSTs them back to the API.

    Args:
        path: Frontend route, for example ``"/reset-password"``.
        uidb64: The encoded user identifier.
        token: The signed token.

    Returns:
        The absolute frontend URL.
    """
    base = str(settings.FRONTEND_BASE_URL).rstrip("/")
    route = "/" + path.strip("/")
    return f"{base}{route}/{uidb64}/{token}"
