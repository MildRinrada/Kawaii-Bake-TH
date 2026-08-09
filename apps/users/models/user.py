"""The custom user model."""

from __future__ import annotations

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.db.models.functions import Lower

from apps.core.models.base import TimeStampedModel
from apps.users.constants import USERNAME_MAX_LENGTH
from apps.users.managers import UserManager
from apps.users.validators.user_validator import validate_username


class User(AbstractBaseUser, PermissionsMixin, TimeStampedModel):
    """An account holder.

    Only credentials and authentication state live here — everything read on
    the auth hot path stays off a join. Presentation data belongs to
    :class:`~apps.users.models.profile.Profile` and private configuration to
    :class:`~apps.users.models.preference.UserPreference`.

    ``email`` is the login identifier; ``username`` is the public URL handle,
    kept separate so an email address never appears in a URL.

    Reverse accessors reserved for future apps (do not reuse these names):
    ``xp_transactions``, ``achievements``, ``gallery_posts``, ``recipes``,
    ``enrollments``, ``reviews``, ``favorites``, ``notifications``.
    """

    email = models.EmailField(
        "email address",
        max_length=254,
        unique=True,
        help_text="Used to sign in. Stored lowercased.",
    )
    username = models.SlugField(
        max_length=USERNAME_MAX_LENGTH,
        unique=True,
        validators=[validate_username],
        help_text="Public handle used in profile URLs.",
    )

    is_active = models.BooleanField(
        default=True,
        help_text=(
            "Authentication kill-switch. Unset to disable sign-in and "
            "invalidate live sessions. Unrelated to email verification."
        ),
    )
    is_staff = models.BooleanField(
        default=False,
        help_text="Whether the user may sign in to the Django admin.",
    )
    is_email_verified = models.BooleanField(
        default=False,
        help_text="Whether the user has confirmed ownership of their email address.",
    )
    email_verified_at = models.DateTimeField(null=True, blank=True)
    deactivated_at = models.DateTimeField(null=True, blank=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    class Meta:
        verbose_name = "user"
        verbose_name_plural = "users"
        ordering = ("-created_at",)
        constraints = [
            # `unique=True` alone is case-sensitive, which would let
            # Bob@x.com and bob@x.com coexist as separate accounts.
            models.UniqueConstraint(
                Lower("email"), name="users_user_email_ci_unique"
            ),
            models.UniqueConstraint(
                Lower("username"), name="users_user_username_ci_unique"
            ),
        ]

    def __str__(self) -> str:
        """Return the public handle (never the email, to keep PII out of logs)."""
        return self.username

    def get_full_name(self) -> str:
        """Return the user's display name, falling back to the handle."""
        return self.username

    def get_short_name(self) -> str:
        """Return the user's short name."""
        return self.username

    @property
    def is_deactivated(self) -> bool:
        """Whether the account has been deactivated."""
        return not self.is_active
