"""Test data builders.

Plain functions rather than a factory library: the manager already guarantees a
complete user, so there is nothing complex to orchestrate.
"""

from __future__ import annotations

from itertools import count
from typing import Any

from apps.users.models import User

VALID_PASSWORD = "Rhubarb!Tart2024"

_sequence = count(1)


def create_user(
    *,
    email: str | None = None,
    username: str | None = None,
    password: str = VALID_PASSWORD,
    **extra: Any,
) -> User:
    """Create a user with a unique email and handle.

    Args:
        email: Explicit email, or ``None`` to generate one.
        username: Explicit handle, or ``None`` to generate one.
        password: Raw password.
        **extra: Additional model field values.

    Returns:
        The created user, with profile and preference rows present.
    """
    index = next(_sequence)
    return User.objects.create_user(
        email=email or f"baker{index}@example.com",
        username=username or f"baker{index}",
        password=password,
        **extra,
    )


def create_verified_user(**kwargs: Any) -> User:
    """Create a user whose email address is already confirmed.

    Args:
        **kwargs: Passed through to :func:`create_user`.

    Returns:
        The created, verified user.
    """
    return create_user(is_email_verified=True, **kwargs)
