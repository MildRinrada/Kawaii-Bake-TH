"""API tests for the staff account-management endpoints."""

from __future__ import annotations

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.users.models import User
from apps.users.tests.factories import create_user


class AdminUserListApiTests(TestCase):
    """GET /api/v1/admin/users/"""

    def setUp(self) -> None:
        self.client = APIClient()
        self.staff = create_user(is_staff=True)
        self.member = create_user()
        self.url = reverse("users_admin:list")

    def test_the_roster_requires_staff(self) -> None:
        self.assertEqual(
            self.client.get(self.url).status_code, status.HTTP_401_UNAUTHORIZED
        )
        self.client.force_login(self.member)
        self.assertEqual(
            self.client.get(self.url).status_code, status.HTTP_403_FORBIDDEN
        )

    def test_the_roster_lists_accounts_with_pii_for_staff(self) -> None:
        self.client.force_login(self.staff)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rows = response.json()["results"]
        usernames = {row["username"] for row in rows}
        self.assertIn(self.member.username, usernames)
        sample = rows[0]
        for key in (
            "email",
            "first_name",
            "last_name",
            "avatar_url",
            "is_active",
            "is_staff",
            "is_email_verified",
            "created_at",
        ):
            self.assertIn(key, sample)

    def test_search_and_flag_filters_narrow_the_roster(self) -> None:
        needle = create_user(username="needlebaker", first_name="Needle")
        create_user(is_staff=True)
        self.client.force_login(self.staff)

        by_search = self.client.get(self.url, {"search": "needlebaker"}).json()
        self.assertEqual(
            [row["username"] for row in by_search["results"]],
            [needle.username],
        )

        staff_only = self.client.get(self.url, {"staff": "true"}).json()
        self.assertTrue(
            all(row["is_staff"] for row in staff_only["results"])
        )

        verified_only = self.client.get(self.url, {"verified": "true"}).json()
        self.assertTrue(
            all(row["is_email_verified"] for row in verified_only["results"])
        )

    def test_an_unknown_filter_is_rejected(self) -> None:
        self.client.force_login(self.staff)

        response = self.client.get(self.url, {"nonsense": "1"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class AdminUserDetailApiTests(TestCase):
    """GET/PATCH /api/v1/admin/users/{id}/"""

    def setUp(self) -> None:
        self.client = APIClient()
        self.staff = create_user(is_staff=True)
        self.member = create_user()

    def _url(self, user_id: int) -> str:
        return reverse("users_admin:detail", kwargs={"user_id": user_id})

    def test_verified_override_stamps_and_clears_the_timestamp(self) -> None:
        self.client.force_login(self.staff)

        turned_on = self.client.patch(
            self._url(self.member.id),
            {"is_email_verified": True},
            format="json",
        )
        self.assertEqual(turned_on.status_code, status.HTTP_200_OK)
        self.member.refresh_from_db()
        self.assertTrue(self.member.is_email_verified)
        self.assertIsNotNone(self.member.email_verified_at)

        turned_off = self.client.patch(
            self._url(self.member.id),
            {"is_email_verified": False},
            format="json",
        )
        self.assertEqual(turned_off.status_code, status.HTTP_200_OK)
        self.member.refresh_from_db()
        self.assertFalse(self.member.is_email_verified)
        self.assertIsNone(self.member.email_verified_at)

    def test_suspension_maintains_deactivated_at_like_self_service(self) -> None:
        self.client.force_login(self.staff)

        self.client.patch(
            self._url(self.member.id), {"is_active": False}, format="json"
        )
        self.member.refresh_from_db()
        self.assertFalse(self.member.is_active)
        self.assertIsNotNone(self.member.deactivated_at)

        self.client.patch(
            self._url(self.member.id), {"is_active": True}, format="json"
        )
        self.member.refresh_from_db()
        self.assertTrue(self.member.is_active)
        self.assertIsNone(self.member.deactivated_at)

    def test_staff_cannot_change_their_own_access_flags(self) -> None:
        self.client.force_login(self.staff)

        response = self.client.patch(
            self._url(self.staff.id), {"is_staff": False}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.json()["error"]["code"], "protected_account")
        self.staff.refresh_from_db()
        self.assertTrue(self.staff.is_staff)

    def test_superuser_flags_are_untouchable_but_names_are_editable(self) -> None:
        boss = User.objects.create_superuser(
            email="boss@example.com", username="bigboss", password="Boss!Pass1"
        )
        self.client.force_login(self.staff)

        flags = self.client.patch(
            self._url(boss.id), {"is_active": False}, format="json"
        )
        self.assertEqual(flags.status_code, status.HTTP_403_FORBIDDEN)

        name = self.client.patch(
            self._url(boss.id), {"first_name": "สมชาย"}, format="json"
        )
        self.assertEqual(name.status_code, status.HTTP_200_OK)
        boss.refresh_from_db()
        self.assertEqual(boss.first_name, "สมชาย")

    def test_legal_name_edit_round_trips(self) -> None:
        self.client.force_login(self.staff)

        response = self.client.patch(
            self._url(self.member.id),
            {"first_name": "  มินตรา ", "last_name": "อบอุ่น"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response.json()
        self.assertEqual(payload["first_name"], "มินตรา")
        self.assertEqual(payload["last_name"], "อบอุ่น")

    def test_unknown_account_is_a_404_and_unknown_key_a_400(self) -> None:
        self.client.force_login(self.staff)

        self.assertEqual(
            self.client.patch(
                self._url(999999), {"first_name": "x"}, format="json"
            ).status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(
            self.client.patch(
                self._url(self.member.id), {"email": "no@example.com"}, format="json"
            ).status_code,
            status.HTTP_400_BAD_REQUEST,
        )


class AdminUserRosterExtrasTests(TestCase):
    """The spec'd roster extras: skill level and the new-users window."""

    def setUp(self) -> None:
        self.client = APIClient()
        self.staff = create_user(is_staff=True)
        self.url = reverse("users_admin:list")

    def test_rows_carry_the_experience_level(self) -> None:
        self.client.force_login(self.staff)

        rows = self.client.get(self.url).json()["results"]

        self.assertIn("experience_level", rows[0])

    def test_joined_days_narrows_to_the_trailing_window(self) -> None:
        from datetime import timedelta

        from django.utils import timezone

        veteran = create_user()
        User.objects.filter(pk=veteran.pk).update(
            created_at=timezone.now() - timedelta(days=90)
        )
        self.client.force_login(self.staff)

        recent = self.client.get(self.url, {"joined_days": 7}).json()

        usernames = {row["username"] for row in recent["results"]}
        self.assertNotIn(veteran.username, usernames)
        self.assertIn(self.staff.username, usernames)
