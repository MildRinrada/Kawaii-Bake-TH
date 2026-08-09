"""Tests for the users read layer, including profile privacy redaction."""

from __future__ import annotations

from datetime import date

from django.test import TestCase

from apps.users.constants import ProfileVisibility
from apps.users.exceptions import ProfileNotVisibleError
from apps.users.selectors import profile_selector, user_selector
from apps.users.tests.factories import create_user


class UserSelectorTests(TestCase):
    """Lookups must be case-insensitive and honour eligibility rules."""

    def test_lookups_are_case_insensitive(self) -> None:
        user = create_user(email="chef@example.com", username="chef")

        self.assertEqual(user_selector.get_by_email(email="CHEF@example.com"), user)
        self.assertEqual(user_selector.get_by_username(username="CHEF"), user)
        self.assertTrue(user_selector.email_exists(email="Chef@Example.com"))
        self.assertTrue(user_selector.username_exists(username="Chef"))

    def test_missing_user_returns_none(self) -> None:
        self.assertIsNone(user_selector.get_by_email(email="nobody@example.com"))

    def test_password_reset_excludes_inactive_users(self) -> None:
        user = create_user(email="gone@example.com", username="gone")
        user.is_active = False
        user.save(update_fields=["is_active"])

        self.assertIsNone(user_selector.get_for_password_reset(email="gone@example.com"))

    def test_password_reset_excludes_unusable_password(self) -> None:
        user = create_user(email="social@example.com", username="social")
        user.set_unusable_password()
        user.save(update_fields=["password"])

        self.assertIsNone(
            user_selector.get_for_password_reset(email="social@example.com")
        )

    def test_get_me_returns_compact_payload(self) -> None:
        user = create_user(username="tiny")

        payload = user_selector.get_me(user_id=user.pk)

        self.assertIsNotNone(payload)
        self.assertEqual(payload.username, "tiny")
        self.assertEqual(payload.id, user.pk)


class ProfileVisibilityTests(TestCase):
    """A hidden profile must be indistinguishable from a missing one."""

    def setUp(self) -> None:
        self.owner = create_user(username="owner")
        self.stranger = create_user(username="stranger")
        profile = self.owner.profile
        profile.location = "Bangkok"
        profile.birthday = date(1995, 5, 5)
        profile.save()

    def _set_visibility(self, visibility: str) -> None:
        preference = self.owner.preference
        preference.profile_visibility = visibility
        preference.save(update_fields=["profile_visibility"])

    def test_public_profile_visible_to_anonymous(self) -> None:
        self._set_visibility(ProfileVisibility.PUBLIC)

        dto = profile_selector.get_visible_profile(username="owner", viewer_id=None)

        self.assertEqual(dto.username, "owner")

    def test_members_only_profile_hidden_from_anonymous(self) -> None:
        self._set_visibility(ProfileVisibility.MEMBERS)

        with self.assertRaises(ProfileNotVisibleError):
            profile_selector.get_visible_profile(username="owner", viewer_id=None)

    def test_members_only_profile_visible_to_signed_in_user(self) -> None:
        self._set_visibility(ProfileVisibility.MEMBERS)

        dto = profile_selector.get_visible_profile(
            username="owner", viewer_id=self.stranger.pk
        )

        self.assertEqual(dto.username, "owner")

    def test_private_profile_hidden_from_others_but_visible_to_owner(self) -> None:
        self._set_visibility(ProfileVisibility.PRIVATE)

        with self.assertRaises(ProfileNotVisibleError):
            profile_selector.get_visible_profile(
                username="owner", viewer_id=self.stranger.pk
            )

        dto = profile_selector.get_visible_profile(
            username="owner", viewer_id=self.owner.pk
        )
        self.assertEqual(dto.username, "owner")

    def test_hidden_fields_are_redacted_for_strangers(self) -> None:
        preference = self.owner.preference
        preference.show_location = False
        preference.show_birthday = False
        preference.save()

        dto = profile_selector.get_visible_profile(
            username="owner", viewer_id=self.stranger.pk
        )

        self.assertIsNone(dto.location)
        self.assertIsNone(dto.birthday)

    def test_owner_always_sees_own_hidden_fields(self) -> None:
        preference = self.owner.preference
        preference.show_location = False
        preference.show_birthday = False
        preference.save()

        dto = profile_selector.get_visible_profile(
            username="owner", viewer_id=self.owner.pk
        )

        self.assertEqual(dto.location, "Bangkok")
        self.assertEqual(dto.birthday, date(1995, 5, 5))

    def test_deactivated_account_is_not_publicly_visible(self) -> None:
        self.owner.is_active = False
        self.owner.save(update_fields=["is_active"])

        with self.assertRaises(ProfileNotVisibleError):
            profile_selector.get_visible_profile(
                username="owner", viewer_id=self.stranger.pk
            )

    def test_unknown_username_raises_the_same_error(self) -> None:
        with self.assertRaises(ProfileNotVisibleError):
            profile_selector.get_visible_profile(username="ghost", viewer_id=None)
