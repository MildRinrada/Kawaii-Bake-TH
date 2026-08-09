"""Credential verification.

This module answers only "are these credentials valid, and may this account
sign in?". Establishing the session is a transport concern and belongs to
``api/credentials/``. Keeping them apart is what lets this logic be tested
without a request object and reused unchanged when JWT replaces cookies.
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.contrib.auth.hashers import make_password

from apps.authentication.exceptions import (
    AccountDisabledError,
    EmailNotVerifiedError,
    InvalidCredentialsError,
)
from apps.authentication.permissions.rate_limit_permissions import (
    clear_login_rate_limit,
    enforce_login_rate_limit,
)
from apps.users.models import User
from apps.users.selectors import user_selector
from apps.users.services import user_service

logger = logging.getLogger("kawaiibake.security")


def authenticate_user(*, email: str, password: str, client_ip: str = "") -> User:
    """Verify credentials and account state.

    Django's ``authenticate()`` is deliberately not used: it collapses every
    failure into ``None``, destroying the distinction between a wrong password,
    a deactivated account and an unverified address that the frontend needs.

    Args:
        email: The submitted email address.
        password: The submitted raw password.
        client_ip: Caller IP, used for throttling.

    Returns:
        The authenticated user.

    Raises:
        RateLimitedError: If too many attempts were made.
        InvalidCredentialsError: If no account matches, or the password is wrong.
        AccountDisabledError: If the account is deactivated.
        EmailNotVerifiedError: If verification is required and missing.
    """
    enforce_login_rate_limit(email=email, client_ip=client_ip)

    user = user_selector.get_by_email(email=email)

    if user is None:
        # Hash anyway so an unknown address takes as long as a known one;
        # otherwise response timing becomes an account-existence oracle.
        make_password(password)
        logger.info("login_failed reason=unknown_email ip=%s", client_ip)
        raise InvalidCredentialsError

    if not user.check_password(password):
        logger.info("login_failed reason=bad_password user_id=%s ip=%s", user.pk, client_ip)
        raise InvalidCredentialsError

    if not user.is_active:
        logger.info("login_failed reason=disabled user_id=%s ip=%s", user.pk, client_ip)
        raise AccountDisabledError

    if settings.REQUIRE_VERIFIED_EMAIL_TO_LOGIN and not user.is_email_verified:
        logger.info("login_failed reason=unverified user_id=%s ip=%s", user.pk, client_ip)
        raise EmailNotVerifiedError

    clear_login_rate_limit(email=email, client_ip=client_ip)
    user_service.record_login(user=user)
    logger.info("login_succeeded user_id=%s ip=%s", user.pk, client_ip)
    return user
