"""Business logic for account state."""

from __future__ import annotations

from apps.users.exceptions import UserNotFoundError
from apps.users.models import User
from apps.users.repositories import user_repository
from apps.users.selectors import user_selector


def create_account(*, email: str, username: str, password: str) -> User:
    """Create a user account with its profile and preference rows.

    This is the public write API other apps use; ``apps.authentication`` calls
    it rather than reaching into this app's repositories.

    Args:
        email: The account email address.
        username: The public handle.
        password: The raw password.

    Returns:
        The created user.
    """
    return user_repository.create_user(email=email, username=username, password=password)


def set_password(*, user: User, raw_password: str) -> None:
    """Replace a user's password.

    Args:
        user: The account being updated.
        raw_password: The new raw password.
    """
    user_repository.set_password(user=user, raw_password=raw_password)


def mark_email_verified(*, user: User) -> None:
    """Record that a user confirmed their email address.

    Args:
        user: The account being verified.
    """
    user_repository.mark_email_verified(user=user)


def record_login(*, user: User) -> None:
    """Stamp a successful sign-in.

    Args:
        user: The account that just signed in.
    """
    user_repository.record_last_login(user=user)


def deactivate_account(*, user_id: int) -> User:
    """Deactivate the caller's account.

    Clearing ``is_active`` both blocks future sign-ins and invalidates existing
    sessions, because the auth backend re-checks the flag on every session
    restore. The row is retained so the account can be restored.

    Args:
        user_id: Primary key of the account to deactivate.

    Returns:
        The deactivated user.

    Raises:
        UserNotFoundError: If the user does not exist.
    """
    user = user_selector.get_by_id(user_id=user_id)
    if user is None:
        raise UserNotFoundError
    user_repository.deactivate(user=user)
    return user


def reactivate_account(*, user_id: int) -> User:
    """Restore a previously deactivated account.

    Args:
        user_id: Primary key of the account to restore.

    Returns:
        The reactivated user.

    Raises:
        UserNotFoundError: If the user does not exist.
    """
    user = user_selector.get_by_id(user_id=user_id)
    if user is None:
        raise UserNotFoundError
    user_repository.activate(user=user)
    return user
