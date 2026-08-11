"""Serializers for profile reads and writes.

Read and write shapes are separate classes on purpose: a single serializer used
for both is how mass-assignment bugs (``is_staff`` in a PATCH body) happen.
"""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.common.api.serializers import StrictSerializer
from apps.users.api.serializers.user_serializers import AvatarUrlMixin, CoverUrlMixin
from apps.users.constants import (
    BIO_MAX_LENGTH,
    DISPLAY_NAME_MAX_LENGTH,
    LOCATION_MAX_LENGTH,
    MAX_FAVORITE_CATEGORIES,
    BakingExperienceLevel,
)


class PublicProfileSerializer(AvatarUrlMixin):
    """Serialises a :class:`~apps.users.selectors.profile_selector.PublicProfileDTO`.

    The DTO has already had the owner's privacy settings applied, so this class
    contains no conditional logic  hidden fields simply arrive as ``None``.
    """

    username = serializers.CharField(read_only=True)
    display_name = serializers.CharField(read_only=True)
    bio = serializers.CharField(read_only=True)
    experience_level = serializers.CharField(read_only=True)
    favorite_categories = serializers.ListField(
        child=serializers.CharField(), read_only=True
    )
    location = serializers.CharField(read_only=True, allow_null=True)
    birthday = serializers.DateField(read_only=True, allow_null=True)
    joined_at = serializers.DateTimeField(read_only=True)


class OwnProfileSerializer(AvatarUrlMixin, CoverUrlMixin):
    """The full profile as seen by its owner.

    Privacy settings are *not* included here; they live behind
    ``/users/preferences/`` so that this payload can never leak them.

    ``cover_url`` is on this shape only. The public profile has no consumer
    for it yet, and an unread field is surface with no test behind it  the
    ``PublicProfileDTO`` gains one the day a public profile page renders it.
    """

    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    # The legal name is owner-only PII, same class as ``email``: it backs
    # certificate printing and never appears on the public profile shape.
    first_name = serializers.CharField(source="user.first_name", read_only=True)
    last_name = serializers.CharField(source="user.last_name", read_only=True)
    is_email_verified = serializers.BooleanField(
        source="user.is_email_verified", read_only=True
    )
    # The caller's *own* staff flag (ADR 0022): lets the shell render the
    # back-office shortcut. Grants nothing - every admin view re-authorises.
    is_staff = serializers.BooleanField(source="user.is_staff", read_only=True)
    joined_at = serializers.DateTimeField(source="user.created_at", read_only=True)

    display_name = serializers.CharField(read_only=True)
    bio = serializers.CharField(read_only=True)
    birthday = serializers.DateField(read_only=True, allow_null=True)
    location = serializers.CharField(read_only=True)
    experience_level = serializers.CharField(read_only=True)
    favorite_categories = serializers.SerializerMethodField()

    def get_favorite_categories(self, obj: Any) -> list[str]:
        """Return the favourite-category slugs (a real relation since Phase 14).

        Sorted for determinism; the selector prefetches the relation, so
        this touches no database.
        """
        return sorted(category.slug for category in obj.favorite_categories.all())


class ProfileUpdateSerializer(StrictSerializer):
    """Validates a profile PATCH payload.

    Every field is optional. Absence means "leave unchanged"; an explicit
    ``null`` on a nullable field means "clear it"  without that distinction a
    user could never remove their birthday.

    Identity and permission fields are absent by construction, so they cannot
    be mass-assigned.
    """

    display_name = serializers.CharField(
        max_length=DISPLAY_NAME_MAX_LENGTH, required=False, allow_blank=True
    )
    bio = serializers.CharField(
        max_length=BIO_MAX_LENGTH, required=False, allow_blank=True
    )
    birthday = serializers.DateField(required=False, allow_null=True)
    location = serializers.CharField(
        max_length=LOCATION_MAX_LENGTH, required=False, allow_blank=True
    )
    experience_level = serializers.ChoiceField(
        choices=BakingExperienceLevel.choices, required=False
    )
    # Slugs, not a frozen enum: membership is validated by the service
    # against the live taxonomy (Phase 14), so an admin-added category is
    # selectable without a code change.
    favorite_categories = serializers.ListField(
        child=serializers.SlugField(max_length=50),
        max_length=MAX_FAVORITE_CATEGORIES,
        required=False,
    )
    avatar = serializers.ImageField(required=False, allow_null=True)
    # Uploaded already cropped by the browser; an explicit null removes it.
    cover = serializers.ImageField(required=False, allow_null=True)
