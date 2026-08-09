"""API tests for the users endpoints."""

from __future__ import annotations

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.users.constants import BakingCategory, ProfileVisibility
from apps.users.tests.factories import create_user


class ProfileApiTests(TestCase):
    """Owner-facing profile endpoints."""

    def setUp(self) -> None:
        cache.clear()
        self.client = APIClient()
        self.user = create_user(username="baker")

    def test_profile_requires_authentication(self) -> None:
        response = self.client.get(reverse("users:profile"))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.json()["error"]["code"], "not_authenticated")

    def test_owner_can_read_own_profile(self) -> None:
        self.client.force_login(self.user)

        response = self.client.get(reverse("users:profile"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["username"], "baker")
        self.assertEqual(response.json()["email"], self.user.email)

    def test_own_profile_exposes_exactly_the_expected_keys(self) -> None:
        self.client.force_login(self.user)

        response = self.client.get(reverse("users:profile"))

        self.assertEqual(
            set(response.json()),
            {
                "avatar_url",
                "username",
                "email",
                "is_email_verified",
                "joined_at",
                "display_name",
                "bio",
                "birthday",
                "location",
                "experience_level",
                "favorite_categories",
            },
        )

    def test_owner_can_update_profile(self) -> None:
        self.client.force_login(self.user)

        response = self.client.patch(
            reverse("users:profile_update"),
            {"bio": "Sourdough obsessive.", "favorite_categories": [BakingCategory.BREAD]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["bio"], "Sourdough obsessive.")
        self.assertEqual(response.json()["favorite_categories"], ["bread"])

    def test_update_rejects_unknown_field(self) -> None:
        self.client.force_login(self.user)

        response = self.client.patch(
            reverse("users:profile_update"),
            {"favourite_categories": ["bread"]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()["error"]["code"], "validation_error")
        self.assertIn("favourite_categories", response.json()["error"]["details"])

    def test_update_rejects_invalid_category(self) -> None:
        self.client.force_login(self.user)

        response = self.client.patch(
            reverse("users:profile_update"),
            {"favorite_categories": ["pizza"]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_cannot_escalate_privileges(self) -> None:
        self.client.force_login(self.user)

        response = self.client.patch(
            reverse("users:profile_update"), {"is_staff": True}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_staff)


class PreferenceApiTests(TestCase):
    """Private preference endpoints."""

    def setUp(self) -> None:
        cache.clear()
        self.client = APIClient()
        self.user = create_user()

    def test_requires_authentication(self) -> None:
        response = self.client.get(reverse("users:preferences"))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_owner_can_read_and_update(self) -> None:
        self.client.force_login(self.user)

        read = self.client.get(reverse("users:preferences"))
        self.assertEqual(read.status_code, status.HTTP_200_OK)

        updated = self.client.patch(
            reverse("users:preferences"),
            {"profile_visibility": ProfileVisibility.PRIVATE, "show_location": False},
            format="json",
        )

        self.assertEqual(updated.status_code, status.HTTP_200_OK)
        self.assertEqual(updated.json()["profile_visibility"], "private")
        self.assertFalse(updated.json()["show_location"])

    def test_invalid_visibility_is_rejected(self) -> None:
        self.client.force_login(self.user)

        response = self.client.patch(
            reverse("users:preferences"), {"profile_visibility": "cosmic"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class PublicProfileApiTests(TestCase):
    """Public profile endpoint and its privacy behaviour."""

    def setUp(self) -> None:
        cache.clear()
        self.client = APIClient()
        self.owner = create_user(username="owner")
        self.stranger = create_user(username="stranger")

    def _url(self, username: str = "owner") -> str:
        return reverse("users:public_profile", kwargs={"username": username})

    def test_public_profile_readable_by_anonymous(self) -> None:
        response = self.client.get(self._url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["username"], "owner")

    def test_public_payload_exposes_exactly_the_expected_keys(self) -> None:
        # Guards against a future field leaking into the public payload.
        response = self.client.get(self._url())

        self.assertEqual(
            set(response.json()),
            {
                "avatar_url",
                "username",
                "display_name",
                "bio",
                "experience_level",
                "favorite_categories",
                "location",
                "birthday",
                "joined_at",
            },
        )

    def test_public_payload_never_contains_private_fields(self) -> None:
        response = self.client.get(self._url())

        for forbidden in ("email", "is_staff", "password", "profile_visibility"):
            self.assertNotIn(forbidden, response.json())

    def test_private_profile_returns_404_not_403(self) -> None:
        preference = self.owner.preference
        preference.profile_visibility = ProfileVisibility.PRIVATE
        preference.save(update_fields=["profile_visibility"])
        self.client.force_login(self.stranger)

        response = self.client.get(self._url())

        # 403 would confirm the account exists; 404 keeps it an unknown.
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unknown_username_returns_404(self) -> None:
        response = self.client.get(self._url("ghost"))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_members_only_profile_hidden_from_anonymous(self) -> None:
        preference = self.owner.preference
        preference.profile_visibility = ProfileVisibility.MEMBERS
        preference.save(update_fields=["profile_visibility"])

        anonymous = self.client.get(self._url())
        self.assertEqual(anonymous.status_code, status.HTTP_404_NOT_FOUND)

        self.client.force_login(self.stranger)
        member = self.client.get(self._url())
        self.assertEqual(member.status_code, status.HTTP_200_OK)


class AccountDeactivationApiTests(TestCase):
    """Account deactivation ends the session and blocks sign-in."""

    def setUp(self) -> None:
        cache.clear()
        self.client = APIClient()
        self.user = create_user()

    def test_deactivate_requires_authentication(self) -> None:
        response = self.client.post(reverse("users:account_deactivate"))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_deactivate_disables_account_and_session(self) -> None:
        self.client.force_login(self.user)

        response = self.client.post(reverse("users:account_deactivate"))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)

        follow_up = self.client.get(reverse("users:profile"))
        self.assertEqual(follow_up.status_code, status.HTTP_401_UNAUTHORIZED)
