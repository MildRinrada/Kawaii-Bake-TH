"""Domain exceptions for the users app."""

from __future__ import annotations

from apps.core.exceptions import DomainError


class EmailAlreadyRegisteredError(DomainError):
    """Raised when an email address is already attached to an account."""

    code = "email_already_registered"
    status_code = 409
    message = "An account with this email address already exists."


class UsernameAlreadyTakenError(DomainError):
    """Raised when a username handle is already claimed."""

    code = "username_taken"
    status_code = 409
    message = "This username is already taken."


class UserNotFoundError(DomainError):
    """Raised when a user cannot be located."""

    code = "user_not_found"
    status_code = 404
    message = "User not found."


class ProfileNotVisibleError(DomainError):
    """Raised when a profile exists but the viewer may not see it.

    Deliberately reported as 404 rather than 403: a 403 would confirm that the
    account exists, which is an enumeration oracle.
    """

    code = "not_found"
    status_code = 404
    message = "User not found."


class ProtectedAccountError(DomainError):
    """Raised when a staff edit would touch an account it must not.

    Two cases: an operator changing their own access flags (locking
    yourself out of the back office should require another operator), and
    anyone changing a superuser's flags through the API.
    """

    code = "protected_account"
    status_code = 403
    message = "This account's access flags cannot be changed here."


class InvalidProfileDataError(DomainError):
    """Raised when profile input violates a domain rule."""

    code = "invalid_profile_data"
    status_code = 400
    message = "The submitted profile data is invalid."
