"""Read-side queries for user accounts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apps.users.models import Profile, User


@dataclass(frozen=True)
class MeDTO:
    """The minimal identity payload used to bootstrap the frontend session."""

    id: int
    username: str
    email: str
    is_email_verified: bool
    is_staff: bool
    experience_level: str
    avatar: Any | None


def get_me(*, user_id: int) -> MeDTO | None:
    """Fetch the compact identity payload for the signed-in user.

    Loads the profile and its user in one query so the serializer never
    traverses an un-prefetched relation.

    Args:
        user_id: Primary key of the signed-in user.

    Returns:
        The identity DTO, or ``None`` when the user has no profile row.
    """
    profile = Profile.objects.select_related("user").filter(pk=user_id).first()
    if profile is None:
        return None
    return MeDTO(
        id=profile.user_id,
        username=profile.user.username,
        email=profile.user.email,
        is_email_verified=profile.user.is_email_verified,
        is_staff=profile.user.is_staff,
        experience_level=profile.experience_level,
        avatar=profile.avatar or None,
    )


def get_by_id(*, user_id: int) -> User | None:
    """Fetch a user by primary key.

    Args:
        user_id: The user's primary key.

    Returns:
        The user, or ``None`` when absent.
    """
    return User.objects.filter(pk=user_id).first()


def get_by_email(*, email: str) -> User | None:
    """Fetch a user by email address, case-insensitively.

    Args:
        email: The address to look up.

    Returns:
        The user, or ``None`` when absent.
    """
    return User.objects.filter(email__iexact=email.strip()).first()


def get_by_username(*, username: str) -> User | None:
    """Fetch a user by public handle, case-insensitively.

    Args:
        username: The handle to look up.

    Returns:
        The user, or ``None`` when absent.
    """
    return User.objects.filter(username__iexact=username.strip()).first()


def email_exists(*, email: str) -> bool:
    """Whether an account already uses this email address.

    Args:
        email: The address to check.

    Returns:
        ``True`` if the address is taken.
    """
    return User.objects.filter(email__iexact=email.strip()).exists()


def username_exists(*, username: str) -> bool:
    """Whether a public handle is already claimed.

    Args:
        username: The handle to check.

    Returns:
        ``True`` if the handle is taken.
    """
    return User.objects.filter(username__iexact=username.strip()).exists()


def active_user_ids() -> list[int]:
    """Primary keys of every active account.

    Part of the public cross-app API: the notifications broadcast
    enumerates its audience through this, so no other app ever queries
    the user table itself. Ids only - no PII crosses the boundary.

    Returns:
        The active account ids.
    """
    return list(User.objects.filter(is_active=True).values_list("id", flat=True))


def get_for_password_reset(*, email: str) -> User | None:
    """Fetch the user eligible to receive a password-reset email.

    Mirrors Django's own ``PasswordResetForm`` filtering: inactive accounts and
    accounts without a usable password (which is how OAuth-only accounts will
    be modelled) must not receive reset mail.

    Args:
        email: The submitted address.

    Returns:
        The eligible user, or ``None``.
    """
    user = User.objects.filter(email__iexact=email.strip(), is_active=True).first()
    if user is None or not user.has_usable_password():
        return None
    return user
