"""Write-side database access for profiles and preferences."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from django.db import transaction

from apps.users.models import Profile, UserPreference


def update_profile(
    *,
    profile: Profile,
    changes: Mapping[str, Any],
    favorite_category_ids: list[int] | None = None,
) -> Profile:
    """Apply changes to a profile atomically.

    Only the supplied keys are written, so a PATCH never clobbers fields the
    client did not mention. Scalar columns and the favourite-category
    relation commit together — an invalid update persists nothing.

    Args:
        profile: The profile to update.
        changes: Scalar field name to new value.
        favorite_category_ids: Replacement category ids (already validated),
            or ``None`` to leave the relation unchanged.

    Returns:
        The updated profile.
    """
    if not changes and favorite_category_ids is None:
        return profile

    with transaction.atomic():
        if changes:
            for field, value in changes.items():
                setattr(profile, field, value)
            profile.save(update_fields=[*changes.keys(), "updated_at"])
        if favorite_category_ids is not None:
            # `.set()` diffs against the current rows — idempotent, and
            # duplicates are impossible through the through-table pair.
            profile.favorite_categories.set(favorite_category_ids)
    return profile


def update_preference(
    *, preference: UserPreference, changes: Mapping[str, Any]
) -> UserPreference:
    """Apply changes to a user's preferences in a single UPDATE.

    Args:
        preference: The preference row to update.
        changes: Field name to new value.

    Returns:
        The updated preferences.
    """
    if not changes:
        return preference

    for field, value in changes.items():
        setattr(preference, field, value)
    preference.save(update_fields=[*changes.keys(), "updated_at"])
    return preference
