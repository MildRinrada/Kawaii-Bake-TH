"""Write-side database access for badge definitions."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from apps.certificates.models import BadgeDefinition


def create_badge(
    *,
    slug: str,
    title_th: str,
    title_en: str,
    description_th: str = "",
    description_en: str = "",
    icon: str = "",
    is_active: bool = True,
) -> BadgeDefinition:
    """Create a badge definition.

    Args:
        slug: Stable identifier; matches an ``AchievementType`` value when
            the badge is awardable by the recalculation rules.
        title_th: Thai display title.
        title_en: English display title.
        description_th: Optional Thai description.
        description_en: Optional English description.
        icon: Frontend asset key under ``public/achievements/``.
        is_active: Whether the catalogue presents the badge.

    Returns:
        The created badge.
    """
    return BadgeDefinition.objects.create(
        slug=slug,
        title_th=title_th,
        title_en=title_en,
        description_th=description_th,
        description_en=description_en,
        icon=icon,
        is_active=is_active,
    )


def update_badge(
    *, badge: BadgeDefinition, changes: Mapping[str, Any]
) -> BadgeDefinition:
    """Apply changes to a badge in a single UPDATE.

    Args:
        badge: The badge to update.
        changes: Field name to new value.

    Returns:
        The updated badge.
    """
    if not changes:
        return badge
    for field, value in changes.items():
        setattr(badge, field, value)
    badge.save(update_fields=list(changes.keys()))
    return badge


def delete_badge(*, badge: BadgeDefinition) -> None:
    """Delete a badge definition.

    Args:
        badge: The badge to delete.

    Raises:
        django.db.models.ProtectedError: If awarded achievements still
            reference the badge; the service maps this to its domain error.
    """
    badge.delete()
