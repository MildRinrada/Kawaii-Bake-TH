"""Staff-initiated account actions (ADR 0031).

The account *lifecycle* endpoints live in ``apps.users``; the actions
here belong to authentication because they mint credentials and email
flows: creating an account, dispatching a password-reset link, and
re-sending the verification email. Authorisation (``IsAdminUser``) is
the view's job.
"""

from __future__ import annotations

import logging

from django.db import IntegrityError

from apps.authentication.exceptions import AccountActionNotApplicableError
from apps.authentication.tasks.email_tasks import (
    send_password_reset_email_task,
    send_verification_email_task,
)
from apps.authentication.validators.registration_validator import (
    validate_password_strength,
    validate_registration,
)
from apps.users.exceptions import EmailAlreadyRegisteredError, UserNotFoundError
from apps.users.models import User
from apps.users.selectors import user_selector
from apps.users.services import user_service
from apps.users.validators.user_validator import (
    normalize_email,
    normalize_username,
)

logger = logging.getLogger("kawaiibake.security")


def admin_create_user(
    *,
    actor_id: int,
    email: str,
    username: str,
    password: str,
    first_name: str = "",
    last_name: str = "",
    verified: bool = False,
) -> User:
    """Create an account on a member's behalf.

    Same validation pipeline as self-service registration, minus the
    rate limit (the caller is staff) and minus the terms stamp - the
    member never consented, so ``terms_accepted_at`` stays empty until
    they do. Unverified accounts get the normal verification email;
    ``verified`` marks the address confirmed immediately (the operator
    vouches for it).

    Args:
        actor_id: The staff member creating the account.
        email: The account email address.
        username: The public handle.
        password: The initial raw password.
        first_name: Legal first name (certificates), optional.
        last_name: Legal last name, optional.
        verified: Mark the email verified instead of sending the email.

    Returns:
        The created user.

    Raises:
        EmailAlreadyRegisteredError: If the email is taken.
        UsernameAlreadyTakenError: If the handle is taken.
        django.core.exceptions.ValidationError: If the handle or
            password is unacceptable.
    """
    email = normalize_email(email)
    username = normalize_username(username)
    validate_registration(email=email, username=username)
    validate_password_strength(password=password)

    try:
        user = user_service.create_account(
            email=email,
            username=username,
            password=password,
            first_name=first_name.strip(),
            last_name=last_name.strip(),
        )
    except IntegrityError as exc:
        raise EmailAlreadyRegisteredError from exc

    if verified:
        user_service.mark_email_verified(user=user)
        user.refresh_from_db(fields=["is_email_verified", "email_verified_at"])
    else:
        send_verification_email_task.delay(user.pk)

    logger.info(
        "account_created_by_staff user_id=%s actor_id=%s verified=%s",
        user.pk,
        actor_id,
        verified,
    )
    return user


def _get_target(user_id: int) -> User:
    user = user_selector.get_by_id(user_id=user_id)
    if user is None:
        raise UserNotFoundError
    return user


def send_password_reset(*, actor_id: int, user_id: int) -> None:
    """Email a password-reset link to one account, staff-initiated.

    Unlike the anonymous request endpoint (which stays silent to avoid
    being an account oracle), the caller here is staff looking at the
    roster - ineligibility is reported honestly instead of swallowed.

    Args:
        actor_id: The staff member requesting the email.
        user_id: The target account.

    Raises:
        UserNotFoundError: If the account does not exist.
        AccountActionNotApplicableError: If the account is deactivated
            or has no usable password (OAuth-only).
    """
    user = _get_target(user_id)
    if not user.is_active:
        raise AccountActionNotApplicableError(
            "Deactivated accounts cannot receive a reset link."
        )
    if not user.has_usable_password():
        raise AccountActionNotApplicableError(
            "This account signs in without a password."
        )
    send_password_reset_email_task.delay(user.pk)
    logger.info(
        "password_reset_sent_by_staff user_id=%s actor_id=%s",
        user_id,
        actor_id,
    )


def resend_verification(*, actor_id: int, user_id: int) -> None:
    """Re-send the email-verification link to one account.

    Args:
        actor_id: The staff member requesting the email.
        user_id: The target account.

    Raises:
        UserNotFoundError: If the account does not exist.
        AccountActionNotApplicableError: If the account is deactivated
            or the email is already verified.
    """
    user = _get_target(user_id)
    if not user.is_active:
        raise AccountActionNotApplicableError(
            "Deactivated accounts cannot receive a verification link."
        )
    if user.is_email_verified:
        raise AccountActionNotApplicableError(
            "This email address is already verified."
        )
    send_verification_email_task.delay(user.pk)
    logger.info(
        "verification_resent_by_staff user_id=%s actor_id=%s",
        user_id,
        actor_id,
    )
