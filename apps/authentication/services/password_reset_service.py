"""Password reset and password change."""

from __future__ import annotations

import logging

from apps.authentication.exceptions import InvalidTokenError
from apps.authentication.permissions.rate_limit_permissions import (
    enforce_password_reset_rate_limit,
)
from apps.authentication.tasks.email_tasks import (
    send_password_changed_email_task,
    send_password_reset_email_task,
)
from apps.authentication.tokens.password_reset_token import password_reset_token
from apps.authentication.utils import decode_uid
from apps.authentication.validators.password_reset_validator import (
    validate_current_password,
    validate_new_password,
)
from apps.users.models import User
from apps.users.selectors import user_selector
from apps.users.services import user_service

logger = logging.getLogger("kawaiibake.security")


def request_password_reset(*, email: str) -> None:
    """Send a reset link if the address belongs to an eligible account.

    Returns nothing and raises nothing on an unknown address: the endpoint must
    respond identically whether or not the account exists, or it becomes an
    enumeration oracle. The throttle is applied before the lookup so timing
    stays flat too.

    Args:
        email: The submitted address.

    Raises:
        RateLimitedError: If too many resets were requested for this address.
    """
    enforce_password_reset_rate_limit(email=email)

    user = user_selector.get_for_password_reset(email=email)
    if user is None:
        logger.info("password_reset_requested result=no_eligible_account")
        return

    logger.info("password_reset_requested user_id=%s", user.pk)
    send_password_reset_email_task.delay(user.pk)


def confirm_password_reset(*, uidb64: str, token: str, new_password: str) -> User:
    """Complete a password reset.

    Setting the password rotates the session-auth hash, so every existing
    session for this user dies on its next request — and the reset token itself
    stops validating, because Django's generator hashes the password.

    Args:
        uidb64: Encoded user identifier from the link.
        token: Signed token from the link.
        new_password: The replacement password.

    Returns:
        The updated user.

    Raises:
        InvalidTokenError: If the link is malformed, unknown or expired.
        django.core.exceptions.ValidationError: If the password is too weak.
    """
    user = _user_from_link(uidb64=uidb64)
    if user is None or not password_reset_token.check_token(user, token):
        raise InvalidTokenError

    validate_new_password(password=new_password, user=user)
    user_service.set_password(user=user, raw_password=new_password)

    logger.info("password_reset_completed user_id=%s", user.pk)
    send_password_changed_email_task.delay(user.pk)
    return user


def change_password(*, user: User, current_password: str, new_password: str) -> User:
    """Change the password of a signed-in user.

    Args:
        user: The signed-in account.
        current_password: The existing password, for confirmation.
        new_password: The replacement password.

    Returns:
        The updated user.

    Raises:
        InvalidCredentialsError: If ``current_password`` is wrong.
        django.core.exceptions.ValidationError: If the new password is too weak.
    """
    validate_current_password(user=user, current_password=current_password)
    validate_new_password(password=new_password, user=user)
    user_service.set_password(user=user, raw_password=new_password)

    logger.info("password_changed user_id=%s", user.pk)
    send_password_changed_email_task.delay(user.pk)
    return user


def _user_from_link(*, uidb64: str) -> User | None:
    """Resolve the user referenced by a signed link.

    Args:
        uidb64: The encoded identifier.

    Returns:
        The user, or ``None`` when the identifier is malformed or unknown.
    """
    user_id = decode_uid(uidb64)
    if user_id is None:
        return None
    return user_selector.get_by_id(user_id=user_id)
