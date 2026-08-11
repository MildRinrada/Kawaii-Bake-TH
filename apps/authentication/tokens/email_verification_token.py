"""Email-verification token generator.

Two deliberate departures from Django's stock generator:

1. **The hash excludes the password and ``last_login``.** The stock
   ``_make_hash_value`` includes both, which would invalidate a verification
   link as soon as the user signs in  an extremely common sequence
   (register, sign in, *then* open the email). ``is_email_verified`` is hashed
   instead, which still makes the token single-use: it stops validating the
   instant verification succeeds.
2. **Its own lifetime.** ``check_token`` reads ``PASSWORD_RESET_TIMEOUT``
   directly from settings, so a subclass cannot otherwise have a different
   expiry. The method is reimplemented to read :attr:`timeout`.
"""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.crypto import constant_time_compare
from django.utils.http import base36_to_int

from apps.authentication.constants import EMAIL_VERIFICATION_SALT


class EmailVerificationToken(PasswordResetTokenGenerator):
    """Single-use, time-limited token confirming ownership of an email address."""

    key_salt = EMAIL_VERIFICATION_SALT

    @property
    def timeout(self) -> int:
        """Token lifetime in seconds."""
        return int(settings.EMAIL_VERIFICATION_TIMEOUT)

    def _make_hash_value(self, user: Any, timestamp: int) -> str:
        """Build the signed payload.

        Includes ``is_email_verified`` so the token self-invalidates on use,
        and the email address so a pending address change voids outstanding
        links. Excludes the password hash and ``last_login`` on purpose.
        """
        email = getattr(user, user.get_email_field_name(), "") or ""
        return f"{user.pk}{email}{user.is_email_verified}{timestamp}"

    def check_token(self, user: Any, token: str | None) -> bool:
        """Validate a verification token against this generator's own timeout.

        Args:
            user: The user the token should belong to.
            token: The token from the verification link.

        Returns:
            ``True`` when the token is authentic and unexpired.
        """
        if not (user and token):
            return False

        try:
            ts_b36, _ = token.split("-")
            timestamp = base36_to_int(ts_b36)
        except ValueError:
            return False

        # Honour SECRET_KEY_FALLBACKS so key rotation does not invalidate
        # every outstanding link.
        for secret in [self.secret, *self.secret_fallbacks]:
            if constant_time_compare(
                self._make_token_with_timestamp(user, timestamp, secret), token
            ):
                break
        else:
            return False

        return (self._num_seconds(self._now()) - timestamp) <= self.timeout


email_verification_token = EmailVerificationToken()
