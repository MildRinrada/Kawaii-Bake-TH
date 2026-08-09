"""Tests for the authentication service layer."""

from __future__ import annotations

from django.core import mail
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings

from apps.authentication.exceptions import (
    AccountDisabledError,
    EmailAlreadyVerifiedError,
    EmailNotVerifiedError,
    InvalidCredentialsError,
    InvalidTokenError,
)
from apps.authentication.services import (
    email_verification_service,
    login_service,
    password_reset_service,
    registration_service,
)
from apps.authentication.tokens.email_verification_token import email_verification_token
from apps.authentication.tokens.password_reset_token import password_reset_token
from apps.authentication.utils import encode_uid
from apps.core.exceptions import RateLimitedError
from apps.users.exceptions import EmailAlreadyRegisteredError, UsernameAlreadyTakenError
from apps.users.tests.factories import VALID_PASSWORD, create_user


class RegistrationServiceTests(TestCase):
    """Account creation rules."""

    def setUp(self) -> None:
        cache.clear()
        mail.outbox.clear()

    def test_register_creates_active_unverified_user(self) -> None:
        user = registration_service.register_user(
            email="New.Baker@Example.com",
            username="newbaker",
            password=VALID_PASSWORD,
            client_ip="1.2.3.4",
        )

        self.assertEqual(user.email, "new.baker@example.com")
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_email_verified)
        self.assertIsNotNone(user.profile)
        self.assertIsNotNone(user.preference)

    def test_register_sends_verification_email(self) -> None:
        registration_service.register_user(
            email="mail@example.com", username="mailer", password=VALID_PASSWORD
        )

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("mail@example.com", mail.outbox[0].to)

    def test_duplicate_email_is_rejected_case_insensitively(self) -> None:
        create_user(email="taken@example.com", username="taken")

        with self.assertRaises(EmailAlreadyRegisteredError):
            registration_service.register_user(
                email="TAKEN@example.com", username="other", password=VALID_PASSWORD
            )

    def test_duplicate_username_is_rejected(self) -> None:
        create_user(email="a@example.com", username="claimed")

        with self.assertRaises(UsernameAlreadyTakenError):
            registration_service.register_user(
                email="b@example.com", username="claimed", password=VALID_PASSWORD
            )

    def test_reserved_username_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            registration_service.register_user(
                email="admin@example.com", username="admin", password=VALID_PASSWORD
            )

    def test_weak_password_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            registration_service.register_user(
                email="weak@example.com", username="weakling", password="password"
            )

    def test_rate_limit_blocks_excessive_registration(self) -> None:
        with override_settings(REGISTRATION_RATE_LIMIT_ATTEMPTS=2):
            registration_service.register_user(
                email="r1@example.com", username="ruser1", password=VALID_PASSWORD,
                client_ip="9.9.9.9",
            )
            registration_service.register_user(
                email="r2@example.com", username="ruser2", password=VALID_PASSWORD,
                client_ip="9.9.9.9",
            )
            with self.assertRaises(RateLimitedError):
                registration_service.register_user(
                    email="r3@example.com", username="ruser3",
                    password=VALID_PASSWORD, client_ip="9.9.9.9",
                )


class LoginServiceTests(TestCase):
    """Credential verification and account-state gating."""

    def setUp(self) -> None:
        cache.clear()
        self.user = create_user(email="chef@example.com", username="chef")

    def test_successful_login_returns_user(self) -> None:
        result = login_service.authenticate_user(
            email="chef@example.com", password=VALID_PASSWORD
        )

        self.assertEqual(result, self.user)

    def test_login_is_case_insensitive_on_email(self) -> None:
        result = login_service.authenticate_user(
            email="CHEF@Example.com", password=VALID_PASSWORD
        )

        self.assertEqual(result, self.user)

    def test_wrong_password_raises_invalid_credentials(self) -> None:
        with self.assertRaises(InvalidCredentialsError):
            login_service.authenticate_user(
                email="chef@example.com", password="WrongPassword!1"
            )

    def test_unknown_email_raises_the_same_error(self) -> None:
        # Identical to the wrong-password case, so the response is not an oracle.
        with self.assertRaises(InvalidCredentialsError):
            login_service.authenticate_user(
                email="nobody@example.com", password=VALID_PASSWORD
            )

    def test_deactivated_account_is_rejected(self) -> None:
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])

        with self.assertRaises(AccountDisabledError):
            login_service.authenticate_user(
                email="chef@example.com", password=VALID_PASSWORD
            )

    @override_settings(REQUIRE_VERIFIED_EMAIL_TO_LOGIN=True)
    def test_unverified_account_rejected_when_verification_required(self) -> None:
        with self.assertRaises(EmailNotVerifiedError):
            login_service.authenticate_user(
                email="chef@example.com", password=VALID_PASSWORD
            )

    def test_unverified_account_allowed_by_default(self) -> None:
        self.assertFalse(self.user.is_email_verified)

        result = login_service.authenticate_user(
            email="chef@example.com", password=VALID_PASSWORD
        )

        self.assertEqual(result, self.user)

    def test_rate_limit_blocks_brute_force(self) -> None:
        with override_settings(LOGIN_RATE_LIMIT_ATTEMPTS=3):
            for _ in range(3):
                with self.assertRaises(InvalidCredentialsError):
                    login_service.authenticate_user(
                        email="chef@example.com", password="Wrong!Password1",
                        client_ip="5.5.5.5",
                    )
            with self.assertRaises(RateLimitedError):
                login_service.authenticate_user(
                    email="chef@example.com", password=VALID_PASSWORD,
                    client_ip="5.5.5.5",
                )


class PasswordResetServiceTests(TestCase):
    """Reset request and confirmation."""

    def setUp(self) -> None:
        cache.clear()
        mail.outbox.clear()
        self.user = create_user(email="reset@example.com", username="resetter")

    def test_request_sends_email_for_known_address(self) -> None:
        password_reset_service.request_password_reset(email="reset@example.com")

        self.assertEqual(len(mail.outbox), 1)

    def test_request_is_silent_for_unknown_address(self) -> None:
        password_reset_service.request_password_reset(email="ghost@example.com")

        self.assertEqual(len(mail.outbox), 0)

    def test_confirm_sets_new_password(self) -> None:
        token = password_reset_token.make_token(self.user)

        password_reset_service.confirm_password_reset(
            uidb64=encode_uid(self.user.pk),
            token=token,
            new_password="Brand!NewSecret9",
        )

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Brand!NewSecret9"))

    def test_token_cannot_be_reused(self) -> None:
        token = password_reset_token.make_token(self.user)
        password_reset_service.confirm_password_reset(
            uidb64=encode_uid(self.user.pk), token=token,
            new_password="Brand!NewSecret9",
        )

        with self.assertRaises(InvalidTokenError):
            password_reset_service.confirm_password_reset(
                uidb64=encode_uid(self.user.pk), token=token,
                new_password="Third!TimeSecret7",
            )

    def test_invalid_uid_is_rejected(self) -> None:
        with self.assertRaises(InvalidTokenError):
            password_reset_service.confirm_password_reset(
                uidb64="bogus", token="bogus", new_password="Brand!NewSecret9"
            )

    def test_weak_new_password_is_rejected(self) -> None:
        token = password_reset_token.make_token(self.user)

        with self.assertRaises(ValidationError):
            password_reset_service.confirm_password_reset(
                uidb64=encode_uid(self.user.pk), token=token, new_password="12345678"
            )

    def test_change_password_requires_current_password(self) -> None:
        with self.assertRaises(InvalidCredentialsError):
            password_reset_service.change_password(
                user=self.user,
                current_password="Wrong!Password1",
                new_password="Brand!NewSecret9",
            )

    def test_change_password_succeeds(self) -> None:
        password_reset_service.change_password(
            user=self.user,
            current_password=VALID_PASSWORD,
            new_password="Brand!NewSecret9",
        )

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Brand!NewSecret9"))


class EmailVerificationServiceTests(TestCase):
    """Email confirmation."""

    def setUp(self) -> None:
        cache.clear()
        mail.outbox.clear()
        self.user = create_user(email="verify@example.com", username="verifier")

    def test_confirm_marks_user_verified(self) -> None:
        token = email_verification_token.make_token(self.user)

        email_verification_service.confirm_email(
            uidb64=encode_uid(self.user.pk), token=token
        )

        self.user.refresh_from_db()
        self.assertTrue(self.user.is_email_verified)
        self.assertIsNotNone(self.user.email_verified_at)

    def test_token_cannot_be_reused(self) -> None:
        token = email_verification_token.make_token(self.user)
        email_verification_service.confirm_email(
            uidb64=encode_uid(self.user.pk), token=token
        )

        with self.assertRaises(EmailAlreadyVerifiedError):
            email_verification_service.confirm_email(
                uidb64=encode_uid(self.user.pk), token=token
            )

    def test_invalid_token_is_rejected(self) -> None:
        with self.assertRaises(InvalidTokenError):
            email_verification_service.confirm_email(
                uidb64=encode_uid(self.user.pk), token="nonsense"
            )

    def test_resend_sends_new_email(self) -> None:
        email_verification_service.resend_verification_email(user=self.user)

        self.assertEqual(len(mail.outbox), 1)

    def test_resend_rejected_when_already_verified(self) -> None:
        self.user.is_email_verified = True
        self.user.save(update_fields=["is_email_verified"])

        with self.assertRaises(EmailAlreadyVerifiedError):
            email_verification_service.resend_verification_email(user=self.user)
