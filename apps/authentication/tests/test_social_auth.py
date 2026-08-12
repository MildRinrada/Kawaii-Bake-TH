"""Google sign-in: what is trusted, what is refused, and what is linked.

Google's own verification is stubbed at the single seam that talks to it
(``_fetch_token_info``) - these tests are about *our* rules, which is
everything that happens after a token is known to be well-formed. The
audience and issuer checks are tested precisely because a real, valid
Google token minted for a different application would pass verification
and must still be refused here.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from apps.authentication.exceptions import (
    AccountDisabledError,
    SocialAuthFailedError,
    SocialAuthUnavailableError,
    SocialEmailUnverifiedError,
)
from apps.authentication.models import SocialAccount
from apps.authentication.services import oauth_service
from apps.users.models import User
from apps.users.tests.factories import create_user

CLIENT_ID = "kawaiibake-test.apps.googleusercontent.com"


def claims(**overrides: Any) -> dict[str, Any]:
    """A token payload as Google's tokeninfo endpoint returns one."""
    payload = {
        "iss": "https://accounts.google.com",
        "aud": CLIENT_ID,
        "sub": "108154321987654321",
        "email": "Neko.Baker@Gmail.com",
        "email_verified": "true",
        "name": "Neko Baker",
    }
    payload.update(overrides)
    return payload


@override_settings(GOOGLE_OAUTH_CLIENT_ID=CLIENT_ID)
class GoogleSignInServiceTests(TestCase):
    """Account resolution: known subject, known address, neither."""

    def setUp(self) -> None:
        cache.clear()

    def sign_in(self, **overrides: Any) -> tuple[User, bool]:
        with patch.object(
            oauth_service, "_fetch_token_info", return_value=claims(**overrides)
        ):
            return oauth_service.sign_in_with_google(credential="stub-token")

    def test_first_sign_in_creates_a_verified_password_less_account(self) -> None:
        user, created = self.sign_in()

        self.assertTrue(created)
        self.assertEqual(user.email, "neko.baker@gmail.com")
        self.assertTrue(user.is_email_verified)
        # No local password exists, which is what keeps password reset from
        # ever mailing this account (see user_selector.get_for_password_reset).
        self.assertFalse(user.has_usable_password())
        # Pressing the button under the consent line *is* the consent event.
        self.assertIsNotNone(user.terms_accepted_at)
        self.assertEqual(SocialAccount.objects.filter(user=user).count(), 1)

    def test_the_handle_is_derived_and_made_unique(self) -> None:
        create_user(username="neko.baker".replace(".", ""), email="taken@example.com")

        user, _created = self.sign_in()

        self.assertNotEqual(user.username, "nekobaker")
        self.assertTrue(user.username.startswith("nekobaker"))
        self.assertTrue(User.objects.filter(username=user.username).exists())

    def test_a_reserved_handle_is_stepped_over(self) -> None:
        user, _created = self.sign_in(email="admin@gmail.com", sub="9001")

        # "admin" is reserved by the username validator; sign-up through a
        # provider must not be a way around that.
        self.assertNotEqual(user.username, "admin")

    def test_second_sign_in_is_the_same_account(self) -> None:
        first, created_first = self.sign_in()
        second, created_second = self.sign_in()

        self.assertTrue(created_first)
        self.assertFalse(created_second)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(SocialAccount.objects.count(), 1)

    def test_a_verified_address_links_to_the_existing_local_account(self) -> None:
        existing = create_user(email="neko.baker@gmail.com", username="localneko")

        user, created = self.sign_in()

        self.assertFalse(created)
        self.assertEqual(user.pk, existing.pk)
        self.assertEqual(SocialAccount.objects.filter(user=existing).count(), 1)
        # Linking must not touch the local password: the account can still
        # sign in the way it always did.
        existing.refresh_from_db()
        self.assertTrue(existing.has_usable_password())

    def test_the_subject_decides_even_when_the_address_changed(self) -> None:
        first, _created = self.sign_in()
        # Same person at Google, new address on the account there.
        moved, created = self.sign_in(email="neko.new@gmail.com")

        self.assertFalse(created)
        self.assertEqual(moved.pk, first.pk)

    def test_a_deactivated_account_cannot_sign_in_through_google(self) -> None:
        create_user(
            email="neko.baker@gmail.com", username="disabledneko", is_active=False
        )

        with self.assertRaises(AccountDisabledError):
            self.sign_in()

    def test_a_token_for_another_application_is_refused(self) -> None:
        with self.assertRaises(SocialAuthFailedError):
            self.sign_in(aud="someone-else.apps.googleusercontent.com")
        self.assertFalse(User.objects.filter(email="neko.baker@gmail.com").exists())

    def test_a_token_from_another_issuer_is_refused(self) -> None:
        with self.assertRaises(SocialAuthFailedError):
            self.sign_in(iss="accounts.evil.example")

    def test_an_unverified_provider_address_is_refused(self) -> None:
        # Accepting it would be the real hole: an unconfirmed address at
        # Google could be someone else's, and address is what links a
        # provider identity to an existing local account.
        with self.assertRaises(SocialEmailUnverifiedError):
            self.sign_in(email_verified="false")

    @override_settings(GOOGLE_OAUTH_CLIENT_ID="")
    def test_without_a_client_id_the_feature_is_unavailable(self) -> None:
        with self.assertRaises(SocialAuthUnavailableError):
            self.sign_in()


@override_settings(GOOGLE_OAUTH_CLIENT_ID=CLIENT_ID)
class GoogleSignInApiTests(TestCase):
    """POST /api/v1/auth/google/"""

    def setUp(self) -> None:
        cache.clear()
        self.client = APIClient()
        self.url = "/api/v1/auth/google/"

    def test_new_account_is_201_and_starts_a_session(self) -> None:
        with patch.object(
            oauth_service, "_fetch_token_info", return_value=claims()
        ):
            response = self.client.post(
                self.url, {"credential": "stub-token"}, format="json"
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.json()["status"], "authenticated")
        # Unlike password registration, this one *does* sign the visitor in:
        # the provider already proved the address, so there is nothing left
        # to confirm by email.
        profile = self.client.get("/api/v1/users/profile/")
        self.assertEqual(profile.status_code, status.HTTP_200_OK)

    def test_returning_account_is_200(self) -> None:
        with patch.object(
            oauth_service, "_fetch_token_info", return_value=claims()
        ):
            self.client.post(self.url, {"credential": "stub"}, format="json")
            self.client.post("/api/v1/auth/logout/")
            again = self.client.post(self.url, {"credential": "stub"}, format="json")

        self.assertEqual(again.status_code, status.HTTP_200_OK)

    def test_a_refused_token_is_401_with_a_stable_code(self) -> None:
        with patch.object(
            oauth_service,
            "_fetch_token_info",
            side_effect=SocialAuthFailedError,
        ):
            response = self.client.post(
                self.url, {"credential": "forged"}, format="json"
            )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.json()["error"]["code"], "social_auth_failed")

    def test_an_empty_body_is_400(self) -> None:
        response = self.client.post(self.url, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("credential", response.json()["error"]["details"])

    @override_settings(GOOGLE_OAUTH_CLIENT_ID="")
    def test_unconfigured_deployment_answers_503(self) -> None:
        response = self.client.post(self.url, {"credential": "x"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(response.json()["error"]["code"], "oauth_unavailable")
