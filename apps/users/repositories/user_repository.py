"""Write-side database access for user accounts."""

from __future__ import annotations

from django.utils import timezone

from apps.users.models import Profile, User, UserPreference


def ensure_related_records(*, user: User) -> None:
    """Guarantee that a user's profile and preference rows exist.

    ``UserManager.create_user`` already creates them, but the Django admin and
    fixtures bypass the manager. Idempotent and race-safe, because both tables
    use the user as their primary key.

    Args:
        user: The user to reconcile.
    """
    Profile.objects.get_or_create(pk=user.pk, defaults={"user": user})
    UserPreference.objects.get_or_create(pk=user.pk, defaults={"user": user})


def create_user(
    *, email: str, username: str, password: str, **extra_fields: object
) -> User:
    """Persist a new user together with its profile and preference rows.

    Args:
        email: The account email address.
        username: The public handle.
        password: The raw password; hashed by the manager.
        **extra_fields: Additional ``User`` column values (legal name,
            consent timestamp), forwarded to the manager verbatim.

    Returns:
        The created user.
    """
    return User.objects.create_user(
        email=email, username=username, password=password, **extra_fields
    )


def set_password(*, user: User, raw_password: str) -> None:
    """Hash and store a new password.

    Changing the password rotates ``get_session_auth_hash``, which invalidates
    every other session for this user on its next request.

    Args:
        user: The user whose password is changing.
        raw_password: The new raw password.
    """
    user.set_password(raw_password)
    user.save(update_fields=["password", "updated_at"])


def mark_email_verified(*, user: User) -> None:
    """Record that the user has confirmed their email address.

    Args:
        user: The user being verified.
    """
    user.is_email_verified = True
    user.email_verified_at = timezone.now()
    user.save(update_fields=["is_email_verified", "email_verified_at", "updated_at"])


def deactivate(*, user: User) -> None:
    """Disable an account.

    Clearing ``is_active`` also invalidates live sessions, because the auth
    backend re-checks it on every session restore.

    Args:
        user: The user to deactivate.
    """
    user.is_active = False
    user.deactivated_at = timezone.now()
    user.save(update_fields=["is_active", "deactivated_at", "updated_at"])


def activate(*, user: User) -> None:
    """Re-enable a previously deactivated account.

    Args:
        user: The user to reactivate.
    """
    user.is_active = True
    user.deactivated_at = None
    user.save(update_fields=["is_active", "deactivated_at", "updated_at"])


def update_account_fields(*, user: User, changes: dict[str, object]) -> User:
    """Apply already-validated column values in a single UPDATE.

    Args:
        user: The user to update.
        changes: Field name to new value.

    Returns:
        The updated user.
    """
    if not changes:
        return user
    for field, value in changes.items():
        setattr(user, field, value)
    user.save(update_fields=[*changes.keys(), "updated_at"])
    return user


def record_last_login(*, user: User) -> None:
    """Stamp the successful sign-in time.

    Args:
        user: The user who just signed in.
    """
    user.last_login = timezone.now()
    user.save(update_fields=["last_login"])
