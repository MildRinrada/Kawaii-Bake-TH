"""Public-facing profile data."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.db import models

from apps.core.models.base import TimeStampedModel
from apps.users.constants import (
    AVATAR_UPLOAD_DIR,
    BIO_MAX_LENGTH,
    DISPLAY_NAME_MAX_LENGTH,
    LOCATION_MAX_LENGTH,
    BakingExperienceLevel,
)
from infrastructure.storage import get_media_storage


def avatar_upload_to(instance: Profile, filename: str) -> str:
    """Build the storage path for an uploaded avatar.

    The original filename is discarded entirely — interpolating user input into
    a storage path invites traversal and collision bugs.

    Args:
        instance: The profile the avatar belongs to.
        filename: The client-supplied filename, used only for its extension.

    Returns:
        A randomised path beneath the avatar directory.
    """
    extension = Path(filename).suffix.lower()
    return f"{AVATAR_UPLOAD_DIR}/{uuid4().hex}{extension}"


class Profile(TimeStampedModel):
    """Presentation data shown on a user's public profile.

    Uses the owning user as its primary key: this guarantees the one-to-one
    relationship at the database level, saves a surrogate key and an index, and
    makes ``get_or_create(pk=user_id)`` race-safe.

    Privacy flags deliberately live on
    :class:`~apps.users.models.preference.UserPreference` instead, so a
    serializer over this model cannot leak them.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="profile",
    )
    display_name = models.CharField(max_length=DISPLAY_NAME_MAX_LENGTH, blank=True)
    bio = models.TextField(max_length=BIO_MAX_LENGTH, blank=True)
    avatar = models.ImageField(
        upload_to=avatar_upload_to,
        # Passed as a callable, not an instance: the migration records the
        # reference, so switching to S3 later needs no schema migration.
        storage=get_media_storage,
        blank=True,
    )
    birthday = models.DateField(null=True, blank=True)
    location = models.CharField(max_length=LOCATION_MAX_LENGTH, blank=True)
    experience_level = models.CharField(
        max_length=20,
        choices=BakingExperienceLevel.choices,
        default=BakingExperienceLevel.BEGINNER,
    )
    # The Phase 1 docstring promised this: "becomes a many-to-many to
    # recipe_categories once that app exists" (ADR 0006). Phase 14 kept the
    # promise — migration 0002 backfilled the JSON slugs into real relations
    # (an exact slug match, as designed). The API shape is unchanged (a list
    # of slugs); validation now runs against the live taxonomy instead of a
    # frozen enum, and a deleted category simply leaves everyone's list.
    # No reverse accessor: nothing consumes "who favors this category" yet.
    favorite_categories = models.ManyToManyField(
        "recipe_categories.RecipeCategory", related_name="+", blank=True
    )

    class Meta:
        verbose_name = "profile"
        verbose_name_plural = "profiles"

    def __str__(self) -> str:
        """Return a readable label for the admin."""
        return f"Profile<{self.user_id}>"
