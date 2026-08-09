"""Email address verification."""

from __future__ import annotations

import logging

from apps.authentication.exceptions import (
    EmailAlreadyVerifiedError,
    InvalidTokenError,
)
from apps.authentication.permissions.rate_limit_permissions import (
    enforce_verification_resend_rate_limit,
)
from apps.authentication.tasks.email_tasks import send_verification_email_task
from apps.authentication.tokens.email_verification_token import email_verification_token
from apps.authentication.utils import decode_uid
from apps.users.models import User
from apps.users.selectors import user_selector
from apps.users.services import user_service

logger = logging.getLogger("kawaiibake.security")


def confirm_email(*, uidb64: str, token: str) -> User:
    """Confirm ownership of an email address.

    The caller is deliberately **not** signed in as a side effect. A forwarded
    or leaked email would otherwise become an account-takeover vector.

    Args:
        uidb64: Encoded user identifier from the link.
        token: Signed token from the link.

    Returns:
        The verified user.

    Raises:
        InvalidTokenError: If the link is malformed, unknown or expired.
        EmailAlreadyVerifiedError: If the address was already confirmed.
    """
    user_id = decode_uid(uidb64)
    user = user_selector.get_by_id(user_id=user_id) if user_id is not None else None
    if user is None:
        raise InvalidTokenError

    if user.is_email_verified:
        # The token also stops validating at this point, since verification
        # state is part of its hash; report the benign case distinctly.
        raise EmailAlreadyVerifiedError

    if not email_verification_token.check_token(user, token):
        raise InvalidTokenError

    user_service.mark_email_verified(user=user)
    logger.info("email_verified user_id=%s", user.pk)
    return user


def resend_verification_email(*, user: User) -> None:
    """Send a fresh confirmation link to a signed-in user.

    Args:
        user: The signed-in account.

    Raises:
        EmailAlreadyVerifiedError: If the address is already confirmed.
        RateLimitedError: If resends were requested too often.
    """
    if user.is_email_verified:
        raise EmailAlreadyVerifiedError

    enforce_verification_resend_rate_limit(user_id=user.pk)
    send_verification_email_task.delay(user.pk)
