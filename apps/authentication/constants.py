"""Enumerations and magic values for the authentication app."""

from __future__ import annotations

from django.db import models


class SocialProvider(models.TextChoices):
    """Identity providers this deployment can sign a visitor in with."""

    GOOGLE = "google", "Google"


# --------------------------------------------------------------------------
# Google sign-in
# --------------------------------------------------------------------------
# Google's own verification endpoint. Using it rather than validating the
# JWT locally is a deliberate trade: one HTTPS round trip per sign-in, and
# no JWKS cache, no clock-skew handling and no crypto dependency of ours to
# get wrong. If sign-in volume ever makes the round trip matter, local
# verification is a swap inside `_fetch_token_info` and nothing else.
GOOGLE_TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"
# The `iss` values Google signs with; both spellings are documented.
GOOGLE_ISSUERS = frozenset({"accounts.google.com", "https://accounts.google.com"})
# A sign-in must not be able to hang a worker on a slow provider.
OAUTH_HTTP_TIMEOUT_SECONDS = 5

# --------------------------------------------------------------------------
# Session lifetime
# --------------------------------------------------------------------------
# "Remember me" checked: the session survives browser restarts for this long.
REMEMBER_ME_SECONDS = 60 * 60 * 24 * 30
# Not checked: session cookie expires when the browser closes.
SESSION_EXPIRE_ON_BROWSER_CLOSE = 0

# --------------------------------------------------------------------------
# Token salts  MUST differ per token type. Sharing a salt would let a
# password-reset token be replayed as an email-verification token.
# --------------------------------------------------------------------------
PASSWORD_RESET_SALT = "kawaiibake.authentication.password_reset"
EMAIL_VERIFICATION_SALT = "kawaiibake.authentication.email_verification"

# --------------------------------------------------------------------------
# Rate-limit key prefixes
# --------------------------------------------------------------------------
RATE_LIMIT_LOGIN = "login"
RATE_LIMIT_REGISTER = "register"
RATE_LIMIT_USERNAME_CHECK = "username_check"
RATE_LIMIT_PASSWORD_RESET = "password_reset"
RATE_LIMIT_VERIFICATION_RESEND = "verification_resend"

# --------------------------------------------------------------------------
# Credential issuer status values. Shipping this envelope now means adding
# two-factor authentication later is additive, not a breaking response change.
# --------------------------------------------------------------------------
STATUS_AUTHENTICATED = "authenticated"
STATUS_MFA_REQUIRED = "mfa_required"

# --------------------------------------------------------------------------
# Email subjects
# --------------------------------------------------------------------------
SUBJECT_VERIFY_EMAIL = "Confirm your KawaiiBake email address"
SUBJECT_PASSWORD_RESET = "Reset your KawaiiBake password"
SUBJECT_PASSWORD_CHANGED = "Your KawaiiBake password was changed"
