"""Structural validation for campaign audience documents (ADR 0030).

An audience is a small JSON object - ``{"kind": ..., ...params}`` - and
this module closes it completely: unknown kinds, unknown keys, missing
or out-of-range params are all rejected before anything touches the
database. Existence checks (does the course exist? do the usernames?)
belong to the service, which resolves audiences against the cross-app
selectors.
"""

from __future__ import annotations

from typing import Any

from apps.notifications.constants import (
    AUDIENCE_DAYS_DEFAULT,
    AUDIENCE_DAYS_MAX,
    AUDIENCE_DAYS_MIN,
    AUDIENCE_USERNAMES_MAX,
    AudienceKind,
)
from apps.notifications.exceptions import InvalidAudienceError
from apps.users.constants import BakingExperienceLevel

# The exact parameter keys each kind accepts, beyond "kind" itself.
_ALLOWED_PARAMS: dict[str, frozenset[str]] = {
    AudienceKind.ALL: frozenset(),
    AudienceKind.ACTIVE: frozenset({"days"}),
    AudienceKind.NEW_USERS: frozenset({"days"}),
    AudienceKind.COURSE_ENROLLED: frozenset({"course_slug"}),
    AudienceKind.COURSE_COMPLETED: frozenset({"course_slug"}),
    AudienceKind.RECIPE_CREATORS: frozenset(),
    AudienceKind.COMMUNITY_CREATORS: frozenset(),
    AudienceKind.SKILL_LEVEL: frozenset({"level"}),
    AudienceKind.SPECIFIC_USERS: frozenset({"usernames"}),
}


def _validated_days(audience: dict[str, Any]) -> int:
    """Return the window in days, defaulted and range-checked."""
    days = audience.get("days", AUDIENCE_DAYS_DEFAULT)
    if not isinstance(days, int) or isinstance(days, bool):
        raise InvalidAudienceError("Audience 'days' must be an integer.")
    if not AUDIENCE_DAYS_MIN <= days <= AUDIENCE_DAYS_MAX:
        raise InvalidAudienceError(
            f"Audience 'days' must be between {AUDIENCE_DAYS_MIN} "
            f"and {AUDIENCE_DAYS_MAX}."
        )
    return days


def validate_audience(audience: Any) -> dict[str, Any]:
    """Validate and normalize one audience document.

    Args:
        audience: The submitted JSON value.

    Returns:
        A normalized copy - defaults filled in, strings stripped.

    Raises:
        InvalidAudienceError: On any structural problem.
    """
    if not isinstance(audience, dict):
        raise InvalidAudienceError("Audience must be an object.")
    kind = audience.get("kind")
    if kind not in AudienceKind.values:
        raise InvalidAudienceError("Unknown audience kind.")

    allowed = _ALLOWED_PARAMS[kind] | {"kind"}
    unknown = set(audience) - allowed
    if unknown:
        raise InvalidAudienceError(
            f"Unknown audience keys: {', '.join(sorted(unknown))}."
        )

    normalized: dict[str, Any] = {"kind": kind}

    if kind in (AudienceKind.ACTIVE, AudienceKind.NEW_USERS):
        normalized["days"] = _validated_days(audience)

    if kind in (AudienceKind.COURSE_ENROLLED, AudienceKind.COURSE_COMPLETED):
        course_slug = audience.get("course_slug")
        if not isinstance(course_slug, str) or not course_slug.strip():
            raise InvalidAudienceError("Audience 'course_slug' is required.")
        normalized["course_slug"] = course_slug.strip()

    if kind == AudienceKind.SKILL_LEVEL:
        level = audience.get("level")
        if level not in BakingExperienceLevel.values:
            raise InvalidAudienceError("Unknown skill level.")
        normalized["level"] = level

    if kind == AudienceKind.SPECIFIC_USERS:
        usernames = audience.get("usernames")
        if not isinstance(usernames, list) or not usernames:
            raise InvalidAudienceError(
                "Audience 'usernames' must be a non-empty list."
            )
        if len(usernames) > AUDIENCE_USERNAMES_MAX:
            raise InvalidAudienceError(
                f"Audience 'usernames' accepts at most "
                f"{AUDIENCE_USERNAMES_MAX} handles."
            )
        cleaned: list[str] = []
        for name in usernames:
            if not isinstance(name, str) or not name.strip():
                raise InvalidAudienceError(
                    "Audience 'usernames' must contain handles only."
                )
            cleaned.append(name.strip())
        normalized["usernames"] = cleaned

    return normalized
