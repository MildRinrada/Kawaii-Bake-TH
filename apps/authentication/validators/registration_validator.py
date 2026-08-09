"""Domain validation for account registration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib.auth.password_validation import validate_password

from apps.users.exceptions import (
    EmailAlreadyRegisteredError,
    UsernameAlreadyTakenError,
)
from apps.users.selectors import user_selector
from apps.users.validators.user_validator import validate_username

if TYPE_CHECKING:  # pragma: no cover - typing only
    from apps.users.models import User


def validate_registration(*, email: str, username: str) -> None:
    """Check that an account may be created with these identifiers.

    Args:
        email: The requested email address.
        username: The requested public handle.

    Raises:
        EmailAlreadyRegisteredError: If the address is taken.
        UsernameAlreadyTakenError: If the handle is taken.
        django.core.exceptions.ValidationError: If the handle is malformed or
            reserved.
    """
    validate_username(username)

    if user_selector.email_exists(email=email):
        raise EmailAlreadyRegisteredError
    if user_selector.username_exists(username=username):
        raise UsernameAlreadyTakenError


def validate_password_strength(*, password: str, user: User | None = None) -> None:
    """Run Django's configured password validators.

    Args:
        password: The raw password.
        user: The account, when known, so similarity checks can run.

    Raises:
        django.core.exceptions.ValidationError: If the password is too weak.
    """
    validate_password(password, user=user)
