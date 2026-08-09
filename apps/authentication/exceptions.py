"""Domain exceptions for the authentication app.

Each carries its own error code and HTTP status, so the shared exception
handler can translate it without any per-view ``try``/``except``.
"""

from __future__ import annotations

from apps.core.exceptions import DomainError


class InvalidCredentialsError(DomainError):
    """Raised when an email/password pair does not match an account.

    The message is deliberately identical whether the email is unknown or the
    password is wrong, so the endpoint is not an account-existence oracle.
    """

    code = "invalid_credentials"
    status_code = 401
    message = "Email or password is incorrect."


class AccountDisabledError(DomainError):
    """Raised when the account exists but has been deactivated."""

    code = "account_disabled"
    status_code = 403
    message = "This account has been deactivated."


class EmailNotVerifiedError(DomainError):
    """Raised when sign-in requires a confirmed email address."""

    code = "email_not_verified"
    status_code = 403
    message = "Please confirm your email address before signing in."


class InvalidTokenError(DomainError):
    """Raised when a reset or verification token is invalid or expired."""

    code = "invalid_token"
    status_code = 400
    message = "This link is invalid or has expired. Please request a new one."


class EmailAlreadyVerifiedError(DomainError):
    """Raised when a verification is attempted on an already-verified address."""

    code = "email_already_verified"
    status_code = 409
    message = "This email address has already been confirmed."


class CredentialRefreshNotSupportedError(DomainError):
    """Raised when refresh is requested from an issuer that has no such concept.

    Session cookies are refreshed by the session engine, so the endpoint exists
    only to keep the JWT contract stable.
    """

    code = "refresh_not_supported"
    status_code = 501
    message = "Credential refresh is not supported by the active auth method."
