"""Staff account-management operations.

Authorisation (``IsAdminUser``) is the view's job; the rules here protect
the platform from its own operators: nobody edits their own access flags,
and superusers are only manageable from the Django shell.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from django.utils import timezone

from apps.users.exceptions import ProtectedAccountError, UserNotFoundError
from apps.users.models import User
from apps.users.repositories import user_repository
from apps.users.selectors import admin_user_selector

logger = logging.getLogger(__name__)

ACCOUNT_EDITABLE_FIELDS = frozenset(
    {"first_name", "last_name", "is_active", "is_staff", "is_email_verified"}
)

# Changing these on yourself could lock the last operator out; changing
# them on a superuser would be privilege escalation by lateral edit.
ACCESS_FLAGS = frozenset({"is_active", "is_staff"})


def get_account(*, user_id: int) -> User:
    """Return one account for the staff detail panel.

    Args:
        user_id: The account's primary key.

    Returns:
        The user with profile preloaded.

    Raises:
        UserNotFoundError: If the account does not exist.
    """
    user = admin_user_selector.get_user(user_id=user_id)
    if user is None:
        raise UserNotFoundError
    return user


def update_account(
    *, actor_id: int, user_id: int, changes: Mapping[str, Any]
) -> User:
    """Validate and apply a staff edit to an account.

    ``is_email_verified`` exists for emergencies (a verification email
    that never arrives): setting it stamps ``email_verified_at`` exactly
    like the self-service flow, clearing it clears the stamp. Toggling
    ``is_active`` maintains ``deactivated_at`` the same way the
    self-service deactivation does.

    Args:
        actor_id: The staff member performing the edit.
        user_id: The account being edited.
        changes: Submitted field values; unknown keys are ignored.

    Returns:
        The updated user.

    Raises:
        UserNotFoundError: If the account does not exist.
        ProtectedAccountError: If the edit touches the actor's own access
            flags or any flag of a superuser.
    """
    user = get_account(user_id=user_id)
    accepted = {k: v for k, v in changes.items() if k in ACCOUNT_EDITABLE_FIELDS}

    flag_changes = {
        field
        for field in (*ACCESS_FLAGS, "is_email_verified")
        if field in accepted and accepted[field] != getattr(user, field)
    }
    if flag_changes & ACCESS_FLAGS and user.pk == actor_id:
        raise ProtectedAccountError
    if flag_changes and user.is_superuser:
        raise ProtectedAccountError

    if "first_name" in accepted:
        accepted["first_name"] = accepted["first_name"].strip()
    if "last_name" in accepted:
        accepted["last_name"] = accepted["last_name"].strip()

    if "is_email_verified" in accepted:
        if accepted["is_email_verified"] and not user.is_email_verified:
            accepted["email_verified_at"] = timezone.now()
        elif not accepted["is_email_verified"] and user.is_email_verified:
            accepted["email_verified_at"] = None

    if "is_active" in accepted:
        if not accepted["is_active"] and user.is_active:
            accepted["deactivated_at"] = timezone.now()
        elif accepted["is_active"] and not user.is_active:
            accepted["deactivated_at"] = None

    updated = user_repository.update_account_fields(user=user, changes=accepted)
    logger.info(
        "account updated by staff",
        extra={
            "user_id": user_id,
            "actor_id": actor_id,
            "fields": sorted(accepted.keys()),
        },
    )
    return updated
