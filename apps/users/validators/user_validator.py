"""Domain validation rules for user accounts."""

from __future__ import annotations

import re

from django.core.exceptions import ValidationError

from apps.users.constants import (
    RESERVED_USERNAMES,
    USERNAME_MAX_LENGTH,
    USERNAME_MIN_LENGTH,
)

USERNAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]*[a-z0-9]$")


def validate_username(value: str) -> None:
    """Validate the shape of a public username handle.

    Args:
        value: The candidate username.

    Raises:
        ValidationError: If the username is malformed or reserved.
    """
    normalized = value.strip().lower()

    if len(normalized) < USERNAME_MIN_LENGTH:
        raise ValidationError(
            f"Username must be at least {USERNAME_MIN_LENGTH} characters long."
        )
    if len(normalized) > USERNAME_MAX_LENGTH:
        raise ValidationError(
            f"Username must be at most {USERNAME_MAX_LENGTH} characters long."
        )
    if not USERNAME_PATTERN.match(normalized):
        raise ValidationError(
            "Username may only contain lowercase letters, numbers, hyphens and "
            "underscores, and must start and end with a letter or number."
        )
    if normalized in RESERVED_USERNAMES:
        raise ValidationError("This username is reserved. Please choose another.")


def normalize_username(value: str) -> str:
    """Return the canonical storage form of a username.

    Args:
        value: The raw username.

    Returns:
        The trimmed, lowercased username.
    """
    return value.strip().lower()


def normalize_email(value: str) -> str:
    """Return the canonical storage form of an email address.

    Django's ``BaseUserManager.normalize_email`` only lowercases the domain,
    which would allow ``Bob@x.com`` and ``bob@x.com`` to coexist. The project
    lowercases the whole address instead.

    Args:
        value: The raw email address.

    Returns:
        The trimmed, fully lowercased address.
    """
    return value.strip().lower()
