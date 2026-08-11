"""API tests for the authentication endpoints."""

from __future__ import annotations

from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.authentication.tokens.email_verification_token import email_verification_token
from apps.authentication.tokens.password_reset_token import password_reset_token
from apps.authentication.utils import encode_uid
from apps.users.models import User
from apps.users.tests.factories import VALID_PASSWORD, create_user


class RegistrationApiTests(TestCase):
    """POST /api/v1/auth/register/"""

    def setUp(self) -> None:
        cache.clear()
        mail.outbox.clear()
        self.client = APIClient()
        self.url = reverse("authentication:register")

    def _payload(self, **overrides: object) -> dict[str, object]:
        payload: dict[str, object] = {
            "email": "new@example.com",
            "username": "newbaker",
            "first_name": "มินตรา",
            "last_name": "อบอุ่น",
            "password": VALID_PASSWORD,
            "password_confirm": VALID_PASSWORD,
            "accept_terms": True,
        }
        payload.update(overrides)
        return payload

    def test_registration_succeeds(self) -> None:
        response = self.client.post(self.url, self._payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.json()["username"], "newbaker")
        self.assertFalse(response.json()["is_email_verified"])
        self.assertTrue(User.objects.filter(email="new@example.com").exists())

    def test_registration_stores_the_legal_name_and_consent(self) -> None:
        response = self.client.post(self.url, self._payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email="new@example.com")
        self.assertEqual(user.first_name, "มินตรา")
        self.assertEqual(user.last_name, "อบอุ่น")
        # PDPA evidence: consenting is what registration *is* now.
        self.assertIsNotNone(user.terms_accepted_at)

    def test_registration_without_a_legal_name_is_rejected(self) -> None:
        for missing in ("first_name", "last_name"):
            payload = self._payload()
            del payload[missing]

            response = self.client.post(self.url, payload, format="json")

            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertIn(missing, response.json()["error"]["details"])
        self.assertFalse(User.objects.filter(email="new@example.com").exists())

    def test_registration_without_consent_is_rejected(self) -> None:
        for consent in (False, None):
            payload = self._payload(accept_terms=consent)
            if consent is None:
                del payload["accept_terms"]

            response = self.client.post(self.url, payload, format="json")

            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertIn("accept_terms", response.json()["error"]["details"])
        self.assertFalse(User.objects.filter(email="new@example.com").exists())

    def test_registration_does_not_return_password(self) -> None:
        response = self.client.post(self.url, self._payload(), format="json")

        self.assertNotIn("password", response.json())

    def test_mismatched_password_confirmation_is_rejected(self) -> None:
        response = self.client.post(
            self.url, self._payload(password_confirm="Different!Pass9"), format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password_confirm", response.json()["error"]["details"])

    def test_duplicate_email_returns_conflict(self) -> None:
        create_user(email="new@example.com", username="existing")

        response = self.client.post(self.url, self._payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.json()["error"]["code"], "email_already_registered")

    def test_reserved_username_is_rejected(self) -> None:
        response = self.client.post(
            self.url, self._payload(username="admin"), format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_weak_password_is_rejected(self) -> None:
        response = self.client.post(
            self.url,
            self._payload(password="password", password_confirm="password"),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_missing_fields_are_reported_per_field(self) -> None:
        response = self.client.post(self.url, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        details = response.json()["error"]["details"]
        self.assertIn("email", details)
        self.assertIn("password", details)


class UsernameAvailabilityApiTests(TestCase):
    """GET /api/v1/auth/username-available/"""

    def setUp(self) -> None:
        cache.clear()
        self.client = APIClient()
        self.url = reverse("authentication:username_available")

    def _check(self, username: str) -> dict[str, object]:
        response = self.client.get(self.url, {"username": username})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return response.json()

    def test_free_username_is_available(self) -> None:
        self.assertEqual(
            self._check("freshbaker"),
            {"username": "freshbaker", "available": True},
        )

    def test_taken_username_is_unavailable_case_insensitively(self) -> None:
        create_user(email="a@example.com", username="mildbakes")

        self.assertFalse(self._check("MildBakes")["available"])

    def test_reserved_username_is_unavailable(self) -> None:
        self.assertFalse(self._check("admin")["available"])

    def test_malformed_username_is_unavailable_not_an_error(self) -> None:
        self.assertFalse(self._check("ab")["available"])
        self.assertFalse(self._check("-dash-edge-")["available"])

    def test_missing_username_param_is_rejected(self) -> None:
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("username", response.json()["error"]["details"])

    def test_checks_are_rate_limited_per_ip(self) -> None:
        with override_settings(USERNAME_CHECK_RATE_LIMIT_ATTEMPTS=2):
            self._check("freshbaker")
            self._check("freshbaker")
            response = self.client.get(self.url, {"username": "freshbaker"})

        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)


class LoginLogoutApiTests(TestCase):
    """POST /api/v1/auth/login/ and /logout/"""

    def setUp(self) -> None:
        cache.clear()
        self.client = APIClient()
        self.user = create_user(email="chef@example.com", username="chef")
        self.login_url = reverse("authentication:login")

    def test_login_succeeds_and_starts_session(self) -> None:
        response = self.client.post(
            self.login_url,
            {"email": "chef@example.com", "password": VALID_PASSWORD},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["status"], "authenticated")
        self.assertEqual(response.json()["user"]["username"], "chef")
        self.assertIn("sessionid", response.cookies)

    def test_login_with_wrong_password_returns_401(self) -> None:
        response = self.client.post(
            self.login_url,
            {"email": "chef@example.com", "password": "Wrong!Password1"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.json()["error"]["code"], "invalid_credentials")

    def test_unknown_email_is_indistinguishable_from_wrong_password(self) -> None:
        unknown = self.client.post(
            self.login_url,
            {"email": "ghost@example.com", "password": VALID_PASSWORD},
            format="json",
        )
        wrong = self.client.post(
            self.login_url,
            {"email": "chef@example.com", "password": "Wrong!Password1"},
            format="json",
        )

        self.assertEqual(unknown.status_code, wrong.status_code)
        self.assertEqual(
            unknown.json()["error"]["message"], wrong.json()["error"]["message"]
        )

    def test_deactivated_account_returns_403(self) -> None:
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])

        response = self.client.post(
            self.login_url,
            {"email": "chef@example.com", "password": VALID_PASSWORD},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.json()["error"]["code"], "account_disabled")

    def test_remember_me_extends_session(self) -> None:
        response = self.client.post(
            self.login_url,
            {
                "email": "chef@example.com",
                "password": VALID_PASSWORD,
                "remember_me": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(self.client.session.get_expiry_age(), 60 * 60 * 24)

    def test_without_remember_me_session_ends_with_browser(self) -> None:
        self.client.post(
            self.login_url,
            {"email": "chef@example.com", "password": VALID_PASSWORD},
            format="json",
        )

        self.assertTrue(self.client.session.get_expire_at_browser_close())

    def test_logout_ends_session(self) -> None:
        self.client.force_login(self.user)

        response = self.client.post(reverse("authentication:logout"))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        follow_up = self.client.get(reverse("users:profile"))
        self.assertEqual(follow_up.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_requires_authentication(self) -> None:
        response = self.client.post(reverse("authentication:logout"))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class MeEndpointTests(TestCase):
    """GET /api/v1/auth/me/"""

    def setUp(self) -> None:
        cache.clear()
        self.client = APIClient()
        self.url = reverse("authentication:me")

    def test_anonymous_returns_200_with_null_user(self) -> None:
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.json()["user"])

    def test_authenticated_returns_identity(self) -> None:
        user = create_user(username="chef")
        self.client.force_login(user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["user"]["username"], "chef")

    def test_identity_reports_the_callers_own_staff_flag(self) -> None:
        # The admin surface decides whether to render from this flag
        # (ADR 0022); it describes the caller and nobody else.
        self.client.force_login(create_user(username="learner"))

        payload = self.client.get(self.url).json()["user"]

        self.assertFalse(payload["is_staff"])

    def test_staff_identity_reports_is_staff_true(self) -> None:
        staff = create_user(username="moderator")
        staff.is_staff = True
        staff.save(update_fields=["is_staff"])
        self.client.force_login(staff)

        payload = self.client.get(self.url).json()["user"]

        self.assertTrue(payload["is_staff"])

    def test_identity_never_exposes_password_material(self) -> None:
        self.client.force_login(create_user(username="chef2"))

        payload = self.client.get(self.url).json()["user"]

        for secret in ("password", "is_superuser", "last_login"):
            self.assertNotIn(secret, payload)


class CsrfEndpointTests(TestCase):
    """GET /api/v1/auth/csrf/ and CSRF enforcement."""

    def setUp(self) -> None:
        cache.clear()

    def test_csrf_endpoint_sets_cookie(self) -> None:
        response = APIClient().get(reverse("authentication:csrf"))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertIn("csrftoken", response.cookies)

    def test_login_without_csrf_token_is_rejected(self) -> None:
        # DRF csrf_exempts every APIView, so unauthenticated POST endpoints are
        # protected explicitly by CsrfProtectedAPIView. This proves it works.
        create_user(email="chef@example.com", username="chef")
        client = APIClient(enforce_csrf_checks=True)

        response = client.post(
            reverse("authentication:login"),
            {"email": "chef@example.com", "password": VALID_PASSWORD},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_login_with_csrf_token_succeeds(self) -> None:
        create_user(email="chef@example.com", username="chef")
        client = APIClient(enforce_csrf_checks=True)
        client.get(reverse("authentication:csrf"))
        token = client.cookies["csrftoken"].value

        response = client.post(
            reverse("authentication:login"),
            {"email": "chef@example.com", "password": VALID_PASSWORD},
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)


class PasswordFlowApiTests(TestCase):
    """Password reset and change endpoints."""

    def setUp(self) -> None:
        cache.clear()
        mail.outbox.clear()
        self.client = APIClient()
        self.user = create_user(email="reset@example.com", username="resetter")

    def test_reset_request_returns_202_for_known_address(self) -> None:
        response = self.client.post(
            reverse("authentication:password_reset"),
            {"email": "reset@example.com"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(len(mail.outbox), 1)

    def test_reset_request_returns_202_for_unknown_address(self) -> None:
        # Identical response and no email: the endpoint must not reveal
        # whether an account exists.
        response = self.client.post(
            reverse("authentication:password_reset"),
            {"email": "ghost@example.com"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(len(mail.outbox), 0)

    def test_reset_confirm_updates_password(self) -> None:
        response = self.client.post(
            reverse("authentication:password_reset_confirm"),
            {
                "uid": encode_uid(self.user.pk),
                "token": password_reset_token.make_token(self.user),
                "new_password": "Brand!NewSecret9",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Brand!NewSecret9"))

    def test_reset_confirm_rejects_bad_token(self) -> None:
        response = self.client.post(
            reverse("authentication:password_reset_confirm"),
            {
                "uid": encode_uid(self.user.pk),
                "token": "not-a-real-token",
                "new_password": "Brand!NewSecret9",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()["error"]["code"], "invalid_token")

    def test_password_change_keeps_caller_signed_in(self) -> None:
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("authentication:password_change"),
            {"current_password": VALID_PASSWORD, "new_password": "Brand!NewSecret9"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        follow_up = self.client.get(reverse("users:profile"))
        self.assertEqual(follow_up.status_code, status.HTTP_200_OK)

    def test_password_change_requires_authentication(self) -> None:
        response = self.client.post(
            reverse("authentication:password_change"),
            {"current_password": VALID_PASSWORD, "new_password": "Brand!NewSecret9"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class EmailVerificationApiTests(TestCase):
    """Email verification endpoints."""

    def setUp(self) -> None:
        cache.clear()
        mail.outbox.clear()
        self.client = APIClient()
        self.user = create_user(email="verify@example.com", username="verifier")

    def test_confirm_marks_verified(self) -> None:
        response = self.client.post(
            reverse("authentication:verify_email"),
            {
                "uid": encode_uid(self.user.pk),
                "token": email_verification_token.make_token(self.user),
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_email_verified)

    def test_confirm_does_not_sign_the_user_in(self) -> None:
        # A forwarded verification email must not become a session.
        self.client.post(
            reverse("authentication:verify_email"),
            {
                "uid": encode_uid(self.user.pk),
                "token": email_verification_token.make_token(self.user),
            },
            format="json",
        )

        response = self.client.get(reverse("authentication:me"))
        self.assertIsNone(response.json()["user"])

    def test_confirm_rejects_bad_token(self) -> None:
        response = self.client.post(
            reverse("authentication:verify_email"),
            {"uid": encode_uid(self.user.pk), "token": "nope"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_resend_requires_authentication(self) -> None:
        response = self.client.post(reverse("authentication:verify_email_resend"))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_resend_sends_email(self) -> None:
        self.client.force_login(self.user)

        response = self.client.post(reverse("authentication:verify_email_resend"))

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(len(mail.outbox), 1)
