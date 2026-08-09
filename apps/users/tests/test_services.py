"""Tests for the users service and repository layers."""

from __future__ import annotations

from datetime import date

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.users.constants import BakingCategory, BakingExperienceLevel, Theme
from apps.users.repositories import user_repository
from apps.users.services import profile_service, user_service
from apps.users.tests.factories import create_user


class ProfileServiceTests(TestCase):
    """Profile updates must validate domain rules and apply partially."""

    def setUp(self) -> None:
        self.user = create_user(username="baker")

    def test_update_applies_only_supplied_fields(self) -> None:
        original_level = self.user.profile.experience_level

        profile = profile_service.update_profile(
            user_id=self.user.pk, changes={"bio": "I love sourdough."}
        )

        self.assertEqual(profile.bio, "I love sourdough.")
        self.assertEqual(profile.experience_level, original_level)

    def test_update_normalises_favorite_categories(self) -> None:
        profile = profile_service.update_profile(
            user_id=self.user.pk,
            changes={
                "favorite_categories": [
                    BakingCategory.BREAD,
                    BakingCategory.CAKE,
                    BakingCategory.BREAD,
                ]
            },
        )

        self.assertEqual(
            sorted(profile.favorite_categories.values_list("slug", flat=True)),
            [BakingCategory.BREAD, BakingCategory.CAKE],
        )

    def test_unknown_category_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            profile_service.update_profile(
                user_id=self.user.pk, changes={"favorite_categories": ["pizza"]}
            )

    def test_future_birthday_is_rejected(self) -> None:
        tomorrow = timezone.localdate() + timezone.timedelta(days=1)

        with self.assertRaises(ValidationError):
            profile_service.update_profile(
                user_id=self.user.pk, changes={"birthday": tomorrow}
            )

    def test_underage_birthday_is_rejected(self) -> None:
        today = timezone.localdate()
        too_young = date(today.year - 10, today.month, today.day)

        with self.assertRaises(ValidationError):
            profile_service.update_profile(
                user_id=self.user.pk, changes={"birthday": too_young}
            )

    def test_birthday_can_be_cleared(self) -> None:
        profile_service.update_profile(
            user_id=self.user.pk, changes={"birthday": date(1990, 1, 1)}
        )

        profile = profile_service.update_profile(
            user_id=self.user.pk, changes={"birthday": None}
        )

        self.assertIsNone(profile.birthday)

    def test_non_editable_fields_are_ignored(self) -> None:
        profile_service.update_profile(
            user_id=self.user.pk, changes={"user_id": 999, "bio": "safe"}
        )

        self.user.refresh_from_db()
        self.assertEqual(self.user.profile.bio, "safe")
        self.assertEqual(self.user.profile.user_id, self.user.pk)

    def test_update_preference(self) -> None:
        preference = profile_service.update_preference(
            user_id=self.user.pk,
            changes={"theme": Theme.DARK, "weekly_goal_minutes": 120},
        )

        self.assertEqual(preference.theme, Theme.DARK)
        self.assertEqual(preference.weekly_goal_minutes, 120)

    def test_unknown_dietary_restriction_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            profile_service.update_preference(
                user_id=self.user.pk, changes={"dietary_restrictions": ["carnivore"]}
            )

    def test_experience_level_can_be_changed(self) -> None:
        profile = profile_service.update_profile(
            user_id=self.user.pk,
            changes={"experience_level": BakingExperienceLevel.ADVANCED},
        )

        self.assertEqual(profile.experience_level, BakingExperienceLevel.ADVANCED)


class AccountServiceTests(TestCase):
    """Account state transitions."""

    def test_deactivate_sets_flag_and_timestamp(self) -> None:
        user = create_user()

        user_service.deactivate_account(user_id=user.pk)

        user.refresh_from_db()
        self.assertFalse(user.is_active)
        self.assertIsNotNone(user.deactivated_at)

    def test_reactivate_clears_timestamp(self) -> None:
        user = create_user()
        user_service.deactivate_account(user_id=user.pk)

        user_service.reactivate_account(user_id=user.pk)

        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertIsNone(user.deactivated_at)


class UserRepositoryTests(TestCase):
    """Repository writes."""

    def test_ensure_related_records_is_idempotent(self) -> None:
        user = create_user()

        user_repository.ensure_related_records(user=user)
        user_repository.ensure_related_records(user=user)

        self.assertIsNotNone(user.profile)
        self.assertIsNotNone(user.preference)

    def test_mark_email_verified(self) -> None:
        user = create_user()

        user_repository.mark_email_verified(user=user)

        user.refresh_from_db()
        self.assertTrue(user.is_email_verified)
        self.assertIsNotNone(user.email_verified_at)

    def test_set_password_changes_hash(self) -> None:
        user = create_user()
        old_hash = user.password

        user_repository.set_password(user=user, raw_password="An0ther!Passphrase")

        user.refresh_from_db()
        self.assertNotEqual(user.password, old_hash)
        self.assertTrue(user.check_password("An0ther!Passphrase"))
