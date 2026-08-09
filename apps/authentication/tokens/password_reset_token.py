"""Password-reset token generator.

Django's stock generator is already correct for this flow: its hash includes
the password hash and ``last_login``, so a token dies the moment the password
changes or the user signs in. Only the salt is overridden, to guarantee a reset
token can never be replayed against another token type.
"""

from __future__ import annotations

from django.contrib.auth.tokens import PasswordResetTokenGenerator

from apps.authentication.constants import PASSWORD_RESET_SALT


class PasswordResetToken(PasswordResetTokenGenerator):
    """Single-use, time-limited token for password resets.

    Lifetime comes from ``settings.PASSWORD_RESET_TIMEOUT``.
    """

    key_salt = PASSWORD_RESET_SALT


password_reset_token = PasswordResetToken()
