"""Attempt throttling for authentication endpoints.

Backed by ``infrastructure.cache`` counters rather than a table, so brute-force
and email-bombing defences cost no schema.

Login is keyed by **IP *and* email**: keying by IP alone both punishes users
behind a shared NAT and is trivially bypassed by rotating addresses.
"""

from __future__ import annotations

from django.conf import settings

from apps.authentication.constants import (
    RATE_LIMIT_LOGIN,
    RATE_LIMIT_PASSWORD_RESET,
    RATE_LIMIT_REGISTER,
    RATE_LIMIT_USERNAME_CHECK,
    RATE_LIMIT_VERIFICATION_RESEND,
)
from apps.core.exceptions import RateLimitedError
from infrastructure.cache import get_rate_limiter


def _enforce(*, key: str, limit: int, window: int) -> None:
    """Record an attempt and raise when the allowance is exhausted.

    Args:
        key: Counter identity.
        limit: Maximum attempts per window.
        window: Window length in seconds.

    Raises:
        RateLimitedError: If the attempt exceeds the allowance.
    """
    status = get_rate_limiter().hit(key, limit=limit, window=window)
    if not status.allowed:
        raise RateLimitedError


def _login_key(*, email: str, client_ip: str) -> str:
    """Build the login counter key."""
    return f"{RATE_LIMIT_LOGIN}:{client_ip}:{email.strip().lower()}"


def enforce_login_rate_limit(*, email: str, client_ip: str) -> None:
    """Throttle sign-in attempts.

    Args:
        email: The submitted email address.
        client_ip: The caller's IP address.

    Raises:
        RateLimitedError: If too many attempts were made.
    """
    _enforce(
        key=_login_key(email=email, client_ip=client_ip),
        limit=settings.LOGIN_RATE_LIMIT_ATTEMPTS,
        window=settings.LOGIN_RATE_LIMIT_WINDOW,
    )


def clear_login_rate_limit(*, email: str, client_ip: str) -> None:
    """Reset the login counter after a successful sign-in.

    Args:
        email: The email address that signed in.
        client_ip: The caller's IP address.
    """
    get_rate_limiter().reset(_login_key(email=email, client_ip=client_ip))


def enforce_registration_rate_limit(*, client_ip: str) -> None:
    """Throttle account creation from a single address.

    Registration reveals whether an email is taken (standard, better UX), so
    throttling is what stops that being used as a bulk enumeration oracle.

    Args:
        client_ip: The caller's IP address.

    Raises:
        RateLimitedError: If too many attempts were made.
    """
    _enforce(
        key=f"{RATE_LIMIT_REGISTER}:{client_ip}",
        limit=settings.REGISTRATION_RATE_LIMIT_ATTEMPTS,
        window=settings.REGISTRATION_RATE_LIMIT_WINDOW,
    )


def enforce_username_check_rate_limit(*, client_ip: str) -> None:
    """Throttle live username-availability checks from a single address.

    Usernames are public handles, so availability is not a secret  the limit
    exists to stop the endpoint being scripted into a bulk enumeration scan.

    Args:
        client_ip: The caller's IP address.

    Raises:
        RateLimitedError: If too many checks were made.
    """
    _enforce(
        key=f"{RATE_LIMIT_USERNAME_CHECK}:{client_ip}",
        limit=settings.USERNAME_CHECK_RATE_LIMIT_ATTEMPTS,
        window=settings.USERNAME_CHECK_RATE_LIMIT_WINDOW,
    )


def enforce_password_reset_rate_limit(*, email: str) -> None:
    """Throttle password-reset requests per address.

    Keyed by email rather than IP so the endpoint cannot be turned into a spam
    amplifier against one victim's inbox.

    Args:
        email: The submitted email address.

    Raises:
        RateLimitedError: If too many attempts were made.
    """
    _enforce(
        key=f"{RATE_LIMIT_PASSWORD_RESET}:{email.strip().lower()}",
        limit=settings.PASSWORD_RESET_RATE_LIMIT_ATTEMPTS,
        window=settings.PASSWORD_RESET_RATE_LIMIT_WINDOW,
    )


def enforce_verification_resend_rate_limit(*, user_id: int) -> None:
    """Throttle "resend verification email" requests.

    Args:
        user_id: The requesting user's primary key.

    Raises:
        RateLimitedError: If too many attempts were made.
    """
    _enforce(
        key=f"{RATE_LIMIT_VERIFICATION_RESEND}:{user_id}",
        limit=settings.PASSWORD_RESET_RATE_LIMIT_ATTEMPTS,
        window=settings.PASSWORD_RESET_RATE_LIMIT_WINDOW,
    )
