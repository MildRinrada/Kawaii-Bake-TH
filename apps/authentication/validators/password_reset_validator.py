"""Domain validation for password reset and change."""

from __future__ import annotations

from typing import TYPE_CHECKING

from apps.authentication.exceptions import InvalidCredentialsError
from apps.authentication.validators.registration_validator import (
    validate_password_strength,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from apps.users.models import User


def validate_new_password(*, password: str, user: User) -> None:
    """Validate a replacement password.

    Args:
        password: The proposed new password.
        user: The account it belongs to.

    Raises:
        django.core.exceptions.ValidationError: If the password is too weak or
            too similar to the user's own attributes.
    """
    validate_password_strength(password=password, user=user)


def validate_current_password(*, user: User, current_password: str) -> None:
    """Confirm the caller knows the existing password.

    Required for self-service password change so that a hijacked session cannot
    be used to lock the real owner out.

    Args:
        user: The account being changed.
        current_password: The password supplied for confirmation.

    Raises:
        InvalidCredentialsError: If the password does not match.
    """
    if not user.check_password(current_password):
        raise InvalidCredentialsError("Your current password is incorrect.")
