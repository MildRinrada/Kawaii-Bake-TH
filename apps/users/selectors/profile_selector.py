"""Read-side queries for profiles and preferences.

The public profile path returns a **redacted DTO** rather than a model
instance. Privacy is therefore applied once, here, and the API layer physically
cannot reach a hidden field. Conditional logic inside a serializer would fail
*open*: the next field someone adds would leak by default.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from apps.users.exceptions import ProfileNotVisibleError
from apps.users.models import Profile, UserPreference
from apps.users.permissions.profile_permissions import can_view_profile


@dataclass(frozen=True)
class PublicProfileDTO:
    """A profile with the owner's privacy settings already applied.

    Every attribute here is safe to serialise for the given viewer. Fields the
    owner has hidden arrive as ``None``.
    """

    username: str
    display_name: str
    bio: str
    avatar: Any | None
    experience_level: str
    favorite_categories: list[str]
    joined_at: datetime
    location: str | None = None
    birthday: date | None = None


@dataclass(frozen=True)
class PersonalizationFact:
    """The explicit personalization facts this domain owns.

    Part of the public cross-app API (Phase 12, extended Phase 14). A
    deliberate subset: the explicitly chosen favourite categories, the
    self-declared experience level and the preferred language  things the
    user *told* the system about their taste. Never anything inferred, and
    nothing privacy-gated (location, birthday), so a consumer cannot leak
    what it never receives (ADR 0020 §2–3).
    """

    experience_level: str
    favorite_category_slugs: tuple[str, ...]
    preferred_language: str


def get_personalization_fact(*, user_id: int) -> PersonalizationFact | None:
    """Fetch the caller's own personalization facts, in two queries.

    Args:
        user_id: Primary key of the user (always the viewer themselves).

    Returns:
        The fact, or ``None`` when the profile is absent.
    """
    row = (
        Profile.objects.filter(pk=user_id)
        .values("experience_level", "user__preference__locale")
        .first()
    )
    if row is None:
        return None
    slugs = tuple(
        Profile.objects.filter(pk=user_id)
        .exclude(favorite_categories__isnull=True)
        .order_by("favorite_categories__slug")
        .values_list("favorite_categories__slug", flat=True)
    )
    return PersonalizationFact(
        experience_level=row["experience_level"],
        favorite_category_slugs=slugs,
        preferred_language=row["user__preference__locale"] or "",
    )


# Own-profile fields that count toward completion. `experience_level` is
# excluded on purpose: it has a non-empty default, so its presence carries
# no signal about the user's intent. Deterministic and derived  never a
# stored counter (ADR 0020 §4).
COMPLETION_FIELDS: tuple[str, ...] = (
    "display_name",
    "bio",
    "avatar",
    "location",
    "birthday",
    "favorite_categories",
)


@dataclass(frozen=True)
class ProfileCompletion:
    """A derived snapshot of how filled-in a profile is."""

    completed: int
    total: int
    percent: int
    missing: tuple[str, ...]


def profile_completion(profile: Profile) -> ProfileCompletion:
    """Compute completion from an already-loaded profile.

    Pure given its input (the favourite-category relation must be
    prefetched or one extra query runs). Privacy settings do not affect
    the count  completion is the owner's private view of their own
    profile, so hiding a field publicly does not un-complete it.

    Args:
        profile: The profile, ideally with categories prefetched.

    Returns:
        The deterministic completion summary.
    """
    missing: list[str] = []
    for field in COMPLETION_FIELDS:
        if field == "favorite_categories":
            filled = bool(profile.favorite_categories.all())
        else:
            filled = bool(getattr(profile, field))
        if not filled:
            missing.append(field)
    total = len(COMPLETION_FIELDS)
    completed = total - len(missing)
    return ProfileCompletion(
        completed=completed,
        total=total,
        percent=round(100 * completed / total),
        missing=tuple(missing),
    )


def get_profile(*, user_id: int) -> Profile | None:
    """Fetch a user's own profile.

    Args:
        user_id: Primary key of the owner.

    Returns:
        The profile, or ``None`` when absent. Favourite categories arrive
        prefetched, so serializing them costs no further query.
    """
    return (
        Profile.objects.select_related("user")
        .prefetch_related("favorite_categories")
        .filter(pk=user_id)
        .first()
    )


def get_preference(*, user_id: int) -> UserPreference | None:
    """Fetch a user's preferences.

    Args:
        user_id: Primary key of the owner.

    Returns:
        The preferences, or ``None`` when absent.
    """
    return UserPreference.objects.select_related("user").filter(pk=user_id).first()


def get_visible_profile(
    *, username: str, viewer_id: int | None, viewer_is_staff: bool = False
) -> PublicProfileDTO:
    """Fetch a profile by handle, redacted for the given viewer.

    Args:
        username: The public handle being requested.
        viewer_id: Primary key of the viewer, or ``None`` when anonymous.
        viewer_is_staff: Whether the viewer is a staff member.

    Returns:
        A :class:`PublicProfileDTO` safe to serialise for this viewer.

    Raises:
        ProfileNotVisibleError: If no such profile exists, the owner is
            deactivated, or the viewer is not permitted to see it. All three
            cases return 404 so the endpoint is not an existence oracle.
    """
    profile = (
        Profile.objects.select_related("user", "user__preference")
        .prefetch_related("favorite_categories")
        .filter(user__username__iexact=username.strip(), user__is_active=True)
        .first()
    )
    if profile is None:
        raise ProfileNotVisibleError

    preference = profile.user.preference
    if not can_view_profile(
        owner_id=profile.user_id,
        visibility=preference.profile_visibility,
        viewer_id=viewer_id,
        viewer_is_staff=viewer_is_staff,
    ):
        raise ProfileNotVisibleError

    is_owner = viewer_id is not None and viewer_id == profile.user_id
    show_location = is_owner or preference.show_location
    show_birthday = is_owner or preference.show_birthday

    return PublicProfileDTO(
        username=profile.user.username,
        display_name=profile.display_name,
        bio=profile.bio,
        avatar=profile.avatar or None,
        experience_level=profile.experience_level,
        favorite_categories=sorted(
            category.slug for category in profile.favorite_categories.all()
        ),
        joined_at=profile.user.created_at,
        location=profile.location if show_location else None,
        birthday=profile.birthday if show_birthday else None,
    )
