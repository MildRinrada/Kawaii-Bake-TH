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


class AccountActionNotApplicableError(DomainError):
    """Raised when a staff account action does not fit the account's
    state - a reset link for a deactivated or password-less account, a
    verification email for an already-verified one."""

    code = "not_applicable"
    status_code = 409
    message = "This action is not applicable to the account's current state."


class SocialAuthUnavailableError(DomainError):
    """Raised when provider sign-in is requested but not configured.

    503, not 404: the endpoint exists and the deployment simply has no
    client id for the provider yet. The frontend hides the button when it
    has no client id either, so reaching this means a mismatch between the
    two halves of the configuration - which is worth an explicit answer
    rather than a silent 404.
    """

    code = "oauth_unavailable"
    status_code = 503
    message = "Google sign-in is not configured on this deployment."


class SocialAuthFailedError(DomainError):
    """Raised when the provider's credential does not check out.

    One code for every reason (expired, wrong audience, forged, wrong
    issuer): the caller can do exactly one thing about all of them, and
    detail here would only help someone probing what we accept.
    """

    code = "social_auth_failed"
    status_code = 401
    message = "Google sign-in could not be verified. Please try again."


class SocialEmailUnverifiedError(DomainError):
    """Raised when the provider itself has not verified the address.

    Separate from the failure above because it is actionable, and because
    accepting it would be the actual security hole: an unverified provider
    address could be someone else's, and email is what links a provider
    identity to an existing local account.
    """

    code = "social_email_unverified"
    status_code = 400
    message = "This Google account has no confirmed email address."
