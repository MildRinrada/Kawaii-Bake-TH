"""Tests for the stateless token generators.

These encode the security properties that replace the token tables.
"""

from __future__ import annotations

from django.test import TestCase

from apps.authentication.tokens.email_verification_token import email_verification_token
from apps.authentication.tokens.password_reset_token import password_reset_token
from apps.users.tests.factories import create_user


class PasswordResetTokenTests(TestCase):
    """Reset tokens must be single-use and unforgeable."""

    def test_token_validates_for_its_own_user(self) -> None:
        user = create_user()
        token = password_reset_token.make_token(user)

        self.assertTrue(password_reset_token.check_token(user, token))

    def test_token_is_invalidated_by_password_change(self) -> None:
        user = create_user()
        token = password_reset_token.make_token(user)

        user.set_password("Compl3tely!Different")
        user.save(update_fields=["password"])

        self.assertFalse(password_reset_token.check_token(user, token))

    def test_token_does_not_validate_for_another_user(self) -> None:
        user = create_user()
        other = create_user()
        token = password_reset_token.make_token(user)

        self.assertFalse(password_reset_token.check_token(other, token))

    def test_garbage_token_is_rejected(self) -> None:
        user = create_user()

        self.assertFalse(password_reset_token.check_token(user, "not-a-token"))
        self.assertFalse(password_reset_token.check_token(user, ""))


class EmailVerificationTokenTests(TestCase):
    """Verification tokens must survive sign-in but die on use."""

    def test_token_validates_for_its_own_user(self) -> None:
        user = create_user()
        token = email_verification_token.make_token(user)

        self.assertTrue(email_verification_token.check_token(user, token))

    def test_token_survives_login_and_password_change(self) -> None:
        # The stock generator hashes the password and last_login, which would
        # kill the link as soon as the user signs in — a very common sequence.
        user = create_user()
        token = email_verification_token.make_token(user)

        user.set_password("An0ther!Passphrase")
        user.save(update_fields=["password"])

        self.assertTrue(email_verification_token.check_token(user, token))

    def test_token_is_single_use(self) -> None:
        user = create_user()
        token = email_verification_token.make_token(user)

        user.is_email_verified = True
        user.save(update_fields=["is_email_verified"])

        self.assertFalse(email_verification_token.check_token(user, token))

    def test_reset_token_cannot_be_replayed_as_verification(self) -> None:
        # Distinct key salts are what make cross-protocol replay impossible.
        user = create_user()
        reset_token = password_reset_token.make_token(user)

        self.assertFalse(email_verification_token.check_token(user, reset_token))

    def test_verification_token_cannot_be_replayed_as_reset(self) -> None:
        user = create_user()
        verify_token = email_verification_token.make_token(user)

        self.assertFalse(password_reset_token.check_token(user, verify_token))
