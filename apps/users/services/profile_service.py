"""Business logic for profiles and preferences.

Services take primitives and return domain objects. They never touch
``request``, never render, and never query the ORM directly.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from django.core.exceptions import ValidationError

from apps.recipe_categories.selectors import category_selector
from apps.users.exceptions import UserNotFoundError
from apps.users.models import Profile, UserPreference
from apps.users.repositories import profile_repository
from apps.users.selectors import profile_selector
from apps.users.validators.profile_validator import (
    validate_avatar,
    validate_birthday,
    validate_cover,
    validate_dietary_restrictions,
    validate_favorite_categories,
)

PROFILE_EDITABLE_FIELDS = frozenset(
    {
        "display_name",
        "bio",
        "avatar",
        "cover",
        "birthday",
        "location",
        "experience_level",
        "favorite_categories",
    }
)

PREFERENCE_EDITABLE_FIELDS = frozenset(
    {
        "profile_visibility",
        "show_birthday",
        "show_location",
        "preferred_difficulty",
        "weekly_goal_minutes",
        "dietary_restrictions",
        "theme",
        "locale",
        "email_course_updates",
        "email_product_updates",
        "email_marketing",
    }
)


def get_own_profile(*, user_id: int) -> Profile:
    """Return the caller's own profile.

    Args:
        user_id: Primary key of the owner.

    Returns:
        The profile.

    Raises:
        UserNotFoundError: If the profile does not exist.
    """
    profile = profile_selector.get_profile(user_id=user_id)
    if profile is None:
        raise UserNotFoundError
    return profile


def get_own_preference(*, user_id: int) -> UserPreference:
    """Return the caller's own preferences.

    Args:
        user_id: Primary key of the owner.

    Returns:
        The preferences.

    Raises:
        UserNotFoundError: If the preferences do not exist.
    """
    preference = profile_selector.get_preference(user_id=user_id)
    if preference is None:
        raise UserNotFoundError
    return preference


def update_profile(*, user_id: int, changes: Mapping[str, Any]) -> Profile:
    """Validate and apply changes to the caller's profile.

    Domain rules are re-checked here rather than trusted from the API layer, so
    the same guarantees hold for any future caller (management command, import).

    Args:
        user_id: Primary key of the owner.
        changes: Submitted field values; unknown keys are ignored.

    Returns:
        The updated profile.

    Raises:
        UserNotFoundError: If the profile does not exist.
        django.core.exceptions.ValidationError: If a domain rule is violated.
    """
    profile = get_own_profile(user_id=user_id)
    accepted = {k: v for k, v in changes.items() if k in PROFILE_EDITABLE_FIELDS}

    # An explicit null on an image field means "remove it". The column is
    # NOT NULL (``blank=True``, not ``null=True``), so the empty string  not
    # ``None``  is what an unset FileField holds; writing ``None`` would fail
    # at save time instead of clearing the picture.
    for field, validate in (("avatar", validate_avatar), ("cover", validate_cover)):
        if field not in accepted:
            continue
        if accepted[field] is None:
            accepted[field] = ""
        else:
            validate(accepted[field])

    if "birthday" in accepted:
        validate_birthday(accepted["birthday"])

    category_ids: list[int] | None = None
    if "favorite_categories" in accepted:
        slugs = validate_favorite_categories(accepted.pop("favorite_categories"))
        # Membership is decided by the live taxonomy, not an enum (Phase 14):
        # `resolve_slugs` returns only active categories, and the diff is
        # this app's own error (ADR 0008  a callee never raises for us).
        resolved = category_selector.resolve_slugs(slugs=slugs)
        unknown = [slug for slug in slugs if slug not in resolved]
        if unknown:
            raise ValidationError(
                f"Unknown baking category: {', '.join(unknown)}."
            )
        category_ids = [resolved[slug] for slug in slugs]

    return profile_repository.update_profile(
        profile=profile, changes=accepted, favorite_category_ids=category_ids
    )


def update_preference(*, user_id: int, changes: Mapping[str, Any]) -> UserPreference:
    """Validate and apply changes to the caller's preferences.

    Args:
        user_id: Primary key of the owner.
        changes: Submitted field values; unknown keys are ignored.

    Returns:
        The updated preferences.

    Raises:
        UserNotFoundError: If the preferences do not exist.
        django.core.exceptions.ValidationError: If a domain rule is violated.
    """
    preference = get_own_preference(user_id=user_id)
    accepted = {k: v for k, v in changes.items() if k in PREFERENCE_EDITABLE_FIELDS}

    if "dietary_restrictions" in accepted:
        accepted["dietary_restrictions"] = validate_dietary_restrictions(
            accepted["dietary_restrictions"]
        )

    return profile_repository.update_preference(preference=preference, changes=accepted)


def get_public_profile(
    *, username: str, viewer_id: int | None, viewer_is_staff: bool = False
) -> profile_selector.PublicProfileDTO:
    """Return a profile redacted according to the owner's privacy settings.

    Args:
        username: The requested public handle.
        viewer_id: Primary key of the viewer, or ``None`` when anonymous.
        viewer_is_staff: Whether the viewer is a staff member.

    Returns:
        The redacted profile DTO.

    Raises:
        ProfileNotVisibleError: If the profile is absent or not visible.
    """
    return profile_selector.get_visible_profile(
        username=username, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )
