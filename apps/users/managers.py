"""Managers for the custom user model."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.contrib.auth.base_user import BaseUserManager
from django.db import transaction
from django.utils import timezone

from apps.users.validators.user_validator import (
    normalize_email as canonical_email,
)
from apps.users.validators.user_validator import (
    normalize_username as canonical_username,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from apps.users.models.user import User


class UserManager(BaseUserManager):
    """Creates users together with their profile and preference rows.

    Account creation is centralised here rather than in a ``post_save`` signal
    so that *every* path — the registration service, ``createsuperuser``, the
    admin, test factories, data migrations — produces a complete user in a
    single transaction. A signal would fire on every save and would need a
    ``created`` guard, a ``raw`` guard, and would make failures surface as
    opaque errors from ``.save()``.
    """

    def get_by_natural_key(self, username: str | None) -> User:
        """Look up a user by email, case-insensitively.

        Args:
            username: The value of ``USERNAME_FIELD`` (an email address).

        Returns:
            The matching user.
        """
        return self.get(email__iexact=username)

    def _create_related_records(self, user: User) -> None:
        """Create the profile and preference rows belonging to ``user``."""
        from apps.users.models.preference import UserPreference
        from apps.users.models.profile import Profile

        Profile.objects.using(self._db).create(user=user)
        UserPreference.objects.using(self._db).create(user=user)

    def _create_user(
        self,
        *,
        email: str,
        username: str,
        password: str | None = None,
        **extra_fields: Any,
    ) -> User:
        """Create a user plus its related rows atomically.

        Args:
            email: The account email address; stored fully lowercased.
            username: The public handle; stored fully lowercased.
            password: Raw password. When omitted the account gets an unusable
                password, which is how OAuth-only accounts will be modelled.
            **extra_fields: Additional model field values.

        Returns:
            The persisted user.

        Raises:
            ValueError: If email or username is missing.
        """
        if not email:
            raise ValueError("Users must have an email address.")
        if not username:
            raise ValueError("Users must have a username.")

        user = self.model(
            email=canonical_email(email),
            username=canonical_username(username),
            **extra_fields,
        )
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()

        with transaction.atomic(using=self._db):
            user.save(using=self._db)
            self._create_related_records(user)
        return user

    def create_user(
        self,
        email: str,
        username: str,
        password: str | None = None,
        **extra_fields: Any,
    ) -> User:
        """Create a standard, non-privileged account.

        New accounts are active but unverified: ``is_active`` is the
        authentication kill-switch, while ``is_email_verified`` gates
        verified-only features. Conflating them would break password reset,
        which filters on ``is_active``.
        """
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        extra_fields.setdefault("is_active", True)
        return self._create_user(
            email=email, username=username, password=password, **extra_fields
        )

    def create_superuser(
        self,
        email: str,
        username: str,
        password: str | None = None,
        **extra_fields: Any,
    ) -> User:
        """Create a staff account with full permissions.

        Raises:
            ValueError: If the staff or superuser flags are overridden to False.
        """
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("is_email_verified", True)
        extra_fields.setdefault("email_verified_at", timezone.now())

        if extra_fields["is_staff"] is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields["is_superuser"] is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self._create_user(
            email=email, username=username, password=password, **extra_fields
        )
