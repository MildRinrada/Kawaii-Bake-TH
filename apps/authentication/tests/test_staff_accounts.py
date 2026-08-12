"""API tests for the staff account actions (ADR 0031)."""

from __future__ import annotations

from django.core import mail
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.users.models import User
from apps.users.tests.factories import create_user


class AdminCreateUserApiTests(TestCase):
    """POST /api/v1/admin/users/create/"""

    def setUp(self) -> None:
        self.client = APIClient()
        self.staff = create_user(is_staff=True)
        self.member = create_user()
        self.url = reverse("auth_admin_accounts:create")

    def _payload(self, **overrides):
        payload = {
            "email": "newbaker@example.com",
            "username": "freshbaker",
            "password": "Whisk!edCream77",
            "first_name": "มินตรา",
            "last_name": "อบอุ่น",
        }
        payload.update(overrides)
        return payload

    def test_create_requires_staff(self) -> None:
        self.assertEqual(
            self.client.post(self.url, self._payload(), format="json").status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.client.force_login(self.member)
        self.assertEqual(
            self.client.post(self.url, self._payload(), format="json").status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_create_sends_verification_and_skips_terms_stamp(self) -> None:
        self.client.force_login(self.staff)

        response = self.client.post(self.url, self._payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertFalse(response.json()["is_email_verified"])
        created = User.objects.get(username="freshbaker")
        self.assertIsNone(created.terms_accepted_at)
        self.assertTrue(created.check_password("Whisk!edCream77"))
        # The verification email went out through the normal task.
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("newbaker@example.com", mail.outbox[0].to)

    def test_create_verified_stamps_instead_of_emailing(self) -> None:
        self.client.force_login(self.staff)

        response = self.client.post(
            self.url, self._payload(verified=True), format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.json()["is_email_verified"])
        created = User.objects.get(username="freshbaker")
        self.assertIsNotNone(created.email_verified_at)
        self.assertEqual(len(mail.outbox), 0)

    def test_create_rejects_taken_email_and_weak_password(self) -> None:
        self.client.force_login(self.staff)

        taken = self.client.post(
            self.url, self._payload(email=self.member.email), format="json"
        )
        self.assertEqual(taken.status_code, status.HTTP_409_CONFLICT)

        weak = self.client.post(
            self.url, self._payload(password="123"), format="json"
        )
        self.assertEqual(weak.status_code, status.HTTP_400_BAD_REQUEST)


class StaffEmailActionApiTests(TestCase):
    """POST .../send-password-reset/ and .../resend-verification/"""

    def setUp(self) -> None:
        self.client = APIClient()
        self.staff = create_user(is_staff=True)
        self.member = create_user()
        self.client.force_login(self.staff)

    def _reset_url(self, user_id: int) -> str:
        return reverse(
            "auth_admin_accounts:send-password-reset", args=[user_id]
        )

    def _verify_url(self, user_id: int) -> str:
        return reverse(
            "auth_admin_accounts:resend-verification", args=[user_id]
        )

    def test_reset_link_sends_for_eligible_accounts_only(self) -> None:
        sent = self.client.post(self._reset_url(self.member.id))
        self.assertEqual(sent.status_code, status.HTTP_200_OK)
        self.assertTrue(sent.json()["sent"])
        self.assertEqual(len(mail.outbox), 1)

        suspended = create_user(is_active=False)
        refused = self.client.post(self._reset_url(suspended.id))
        self.assertEqual(refused.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(refused.json()["error"]["code"], "not_applicable")

        self.assertEqual(
            self.client.post(self._reset_url(999_999)).status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_verification_resend_honours_account_state(self) -> None:
        unverified = create_user(is_email_verified=False)
        sent = self.client.post(self._verify_url(unverified.id))
        self.assertEqual(sent.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 1)

        verified = create_user(is_email_verified=True)
        refused = self.client.post(self._verify_url(verified.id))
        self.assertEqual(refused.status_code, status.HTTP_409_CONFLICT)
