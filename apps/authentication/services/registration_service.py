"""Account registration."""

from __future__ import annotations

import logging

from django.core.exceptions import ValidationError
from django.db import IntegrityError

from apps.authentication.permissions.rate_limit_permissions import (
    enforce_registration_rate_limit,
    enforce_username_check_rate_limit,
)
from apps.authentication.tasks.email_tasks import send_verification_email_task
from apps.authentication.validators.registration_validator import (
    validate_password_strength,
    validate_registration,
)
from apps.users.exceptions import EmailAlreadyRegisteredError
from apps.users.models import User
from apps.users.selectors import user_selector
from apps.users.services import user_service
from apps.users.validators.user_validator import (
    normalize_email,
    normalize_username,
    validate_username,
)

logger = logging.getLogger("kawaiibake.security")


def is_username_available(*, username: str, client_ip: str = "") -> bool:
    """Answer whether a handle could be registered right now.

    A malformed or reserved handle reports unavailable rather than raising:
    the caller is a live as-you-type check, and "you cannot have this" is the
    only fact it needs. The definitive verdict remains ``register_user`` —
    two racing sign-ups are still settled by the unique constraint.

    Args:
        username: The candidate handle.
        client_ip: Caller IP, used for throttling.

    Returns:
        True when the handle is well-formed, unreserved and unclaimed.

    Raises:
        RateLimitedError: If too many checks were made from this address.
    """
    enforce_username_check_rate_limit(client_ip=client_ip)

    normalized = normalize_username(username)
    try:
        validate_username(normalized)
    except ValidationError:
        return False
    return not user_selector.username_exists(username=normalized)


def register_user(
    *, email: str, username: str, password: str, client_ip: str = ""
) -> User:
    """Create an account and dispatch its verification email.

    New accounts are active but unverified: ``is_active`` is the authentication
    kill-switch, while ``is_email_verified`` gates verified-only features.

    Args:
        email: The requested email address.
        username: The requested public handle.
        password: The raw password.
        client_ip: Caller IP, used for throttling.

    Returns:
        The created user.

    Raises:
        RateLimitedError: If too many accounts were created from this address.
        EmailAlreadyRegisteredError: If the email is taken.
        UsernameAlreadyTakenError: If the handle is taken.
        django.core.exceptions.ValidationError: If the handle or password is
            unacceptable.
    """
    enforce_registration_rate_limit(client_ip=client_ip)

    email = normalize_email(email)
    username = normalize_username(username)

    validate_registration(email=email, username=username)
    validate_password_strength(password=password)

    try:
        user = user_service.create_account(
            email=email, username=username, password=password
        )
    except IntegrityError as exc:
        # Two concurrent registrations can both pass the existence check; the
        # database unique constraint is the real arbiter.
        raise EmailAlreadyRegisteredError from exc

    logger.info("account_registered user_id=%s ip=%s", user.pk, client_ip)
    send_verification_email_task.delay(user.pk)
    return user
