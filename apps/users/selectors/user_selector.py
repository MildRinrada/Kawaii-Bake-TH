"""Read-side queries for user accounts."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from django.utils import timezone

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


def recently_joined_ids(*, days: int) -> list[int]:
    """Active accounts created within the last ``days`` days.

    Part of the cross-app audience API (ADR 0030): campaign targeting
    enumerates users through these selectors so no other app queries the
    user table itself. Ids only - no PII crosses the boundary.

    Args:
        days: The joined-within window, in days.

    Returns:
        The matching account ids.
    """
    since = timezone.now() - timedelta(days=days)
    return list(
        User.objects.filter(is_active=True, created_at__gte=since).values_list(
            "id", flat=True
        )
    )


def recently_active_ids(*, days: int) -> list[int]:
    """Active accounts that signed in within the last ``days`` days.

    "Active" here is honest to what the platform records: ``last_login``
    is stamped by sign-in, so an account that stays signed in for months
    ages out of this audience. Ids only.

    Args:
        days: The signed-in-within window, in days.

    Returns:
        The matching account ids.
    """
    since = timezone.now() - timedelta(days=days)
    return list(
        User.objects.filter(is_active=True, last_login__gte=since).values_list(
            "id", flat=True
        )
    )


def ids_by_experience_level(*, level: str) -> list[int]:
    """Active accounts whose profile declares this baking skill level.

    Args:
        level: A value of :class:`apps.users.constants.BakingExperienceLevel`.

    Returns:
        The matching account ids.
    """
    return list(
        User.objects.filter(
            is_active=True, profile__experience_level=level
        ).values_list("id", flat=True)
    )


def match_usernames(*, usernames: list[str]) -> tuple[list[int], list[str]]:
    """Resolve public handles to active account ids, case-insensitively.

    Args:
        usernames: The handles to resolve.

    Returns:
        ``(ids, missing)`` - the matched active account ids, and the
        submitted handles that matched no active account.
    """
    cleaned = [name.strip() for name in usernames if name.strip()]
    rows = User.objects.filter(
        is_active=True, username__in=cleaned
    ).values_list("id", "username")
    by_lower = {username.lower(): user_id for user_id, username in rows}
    ids: list[int] = []
    missing: list[str] = []
    for name in cleaned:
        user_id = by_lower.get(name.lower())
        if user_id is None:
            missing.append(name)
        elif user_id not in ids:
            ids.append(user_id)
    return ids, missing


def filter_active(*, user_ids: Sequence[int]) -> list[int]:
    """Keep only the ids that belong to active accounts.

    Audiences derived from content (enrollments, authorship) may contain
    deactivated accounts; delivery must not.

    Args:
        user_ids: Candidate account ids.

    Returns:
        The subset that is active.
    """
    return list(
        User.objects.filter(is_active=True, id__in=user_ids).values_list(
            "id", flat=True
        )
    )


def display_names(*, user_ids: Sequence[int]) -> dict[int, str]:
    """Public display names for a set of accounts, handle as fallback.

    Only public identity leaves this function - the display name and
    handle are both rendered on public profiles already.

    Args:
        user_ids: The account ids to name.

    Returns:
        Mapping of account id to its public display name.
    """
    rows = User.objects.filter(id__in=user_ids).values_list(
        "id", "username", "profile__display_name"
    )
    return {
        user_id: (display_name or username)
        for user_id, username, display_name in rows
    }


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
