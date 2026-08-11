"""Staff curation of badge definitions.

Badges are presentation metadata: creating one here does not award
anything (awarding stays with ``achievement_service.recalculate``), and
deleting one is only possible while nothing references it - retiring a
badge that has been earned is done by deactivating it.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from django.db.models import ProtectedError, QuerySet

from apps.certificates.exceptions import (
    BadgeInUseError,
    BadgeNotFoundError,
    DuplicateBadgeSlugError,
)
from apps.certificates.models import BadgeDefinition
from apps.certificates.repositories import badge_repository
from apps.certificates.selectors import badge_selector

logger = logging.getLogger(__name__)

BADGE_EDITABLE_FIELDS = frozenset(
    {
        "slug",
        "title_th",
        "title_en",
        "description_th",
        "description_en",
        "icon",
        "is_active",
    }
)


def list_badges() -> QuerySet[BadgeDefinition]:
    """Return every badge for the staff surface, awarded counts included.

    Returns:
        A lazy queryset annotated with ``awarded_count``.
    """
    return badge_selector.list_all()


def _require_badge(slug: str) -> BadgeDefinition:
    badge = badge_selector.get_by_slug(slug=slug)
    if badge is None:
        raise BadgeNotFoundError
    return badge


def _require_free_slug(slug: str, *, exclude_id: int | None = None) -> None:
    existing = badge_selector.get_by_slug(slug=slug)
    if existing is not None and existing.id != exclude_id:
        raise DuplicateBadgeSlugError


def create_badge(*, actor_id: int, slug: str, **fields: Any) -> BadgeDefinition:
    """Create a badge definition on behalf of a staff member.

    Args:
        actor_id: Primary key of the staff member, for the audit log.
        slug: Stable identifier.
        **fields: ``title_th``, ``title_en`` and the optional columns.

    Returns:
        The created badge, annotated with ``awarded_count``.

    Raises:
        DuplicateBadgeSlugError: If the slug is already taken.
    """
    cleaned = slug.strip()
    _require_free_slug(cleaned)
    badge = badge_repository.create_badge(slug=cleaned, **fields)
    logger.info(
        "badge created", extra={"badge_slug": cleaned, "actor_id": actor_id}
    )
    return _require_badge(badge.slug)


def update_badge(
    *, actor_id: int, slug: str, changes: Mapping[str, Any]
) -> BadgeDefinition:
    """Validate and apply changes to a badge definition.

    Args:
        actor_id: Primary key of the staff member, for the audit log.
        slug: The badge being edited.
        changes: Submitted field values; unknown keys are ignored.

    Returns:
        The updated badge, annotated with ``awarded_count``.

    Raises:
        BadgeNotFoundError: If the badge does not exist.
        DuplicateBadgeSlugError: If a rename collides with another slug.
    """
    badge = _require_badge(slug)
    accepted = {k: v for k, v in changes.items() if k in BADGE_EDITABLE_FIELDS}

    if "slug" in accepted:
        accepted["slug"] = accepted["slug"].strip()
        _require_free_slug(accepted["slug"], exclude_id=badge.id)

    badge_repository.update_badge(badge=badge, changes=accepted)
    logger.info(
        "badge updated",
        extra={
            "badge_slug": badge.slug,
            "actor_id": actor_id,
            "fields": sorted(accepted.keys()),
        },
    )
    return _require_badge(badge.slug)


def delete_badge(*, actor_id: int, slug: str) -> None:
    """Delete a badge definition that nothing references yet.

    Args:
        actor_id: Primary key of the staff member, for the audit log.
        slug: The badge to delete.

    Raises:
        BadgeNotFoundError: If the badge does not exist.
        BadgeInUseError: If awarded achievements reference the badge.
    """
    badge = _require_badge(slug)
    try:
        badge_repository.delete_badge(badge=badge)
    except ProtectedError as error:
        raise BadgeInUseError from error
    logger.info("badge deleted", extra={"badge_slug": slug, "actor_id": actor_id})
