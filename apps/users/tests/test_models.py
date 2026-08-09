"""Tests for the user model and its manager."""

from __future__ import annotations

from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.users.models import Profile, User, UserPreference
from apps.users.tests.factories import VALID_PASSWORD, create_user


class UserManagerTests(TestCase):
    """The manager must always produce a complete, correctly hashed user."""

    def test_create_user_creates_profile_and_preference(self) -> None:
        user = create_user()

        self.assertTrue(Profile.objects.filter(pk=user.pk).exists())
        self.assertTrue(UserPreference.objects.filter(pk=user.pk).exists())

    def test_password_is_hashed_not_stored_raw(self) -> None:
        user = create_user()

        self.assertNotEqual(user.password, VALID_PASSWORD)
        self.assertTrue(user.check_password(VALID_PASSWORD))

    def test_email_and_username_are_lowercased(self) -> None:
        user = create_user(email="Mixed.Case@Example.COM", username="MixedCase")

        self.assertEqual(user.email, "mixed.case@example.com")
        self.assertEqual(user.username, "mixedcase")

    def test_new_accounts_are_active_but_unverified(self) -> None:
        user = create_user()

        self.assertTrue(user.is_active)
        self.assertFalse(user.is_email_verified)

    def test_email_uniqueness_is_case_insensitive(self) -> None:
        create_user(email="baker@example.com", username="one")

        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create_user(
                email="BAKER@example.com", username="two", password=VALID_PASSWORD
            )

    def test_username_uniqueness_is_case_insensitive(self) -> None:
        create_user(email="a@example.com", username="croissant")

        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create_user(
                email="b@example.com", username="Croissant", password=VALID_PASSWORD
            )

    def test_create_user_requires_email_and_username(self) -> None:
        with self.assertRaises(ValueError):
            User.objects.create_user(email="", username="x", password=VALID_PASSWORD)
        with self.assertRaises(ValueError):
            User.objects.create_user(
                email="x@example.com", username="", password=VALID_PASSWORD
            )

    def test_create_superuser_is_staff_and_verified(self) -> None:
        user = User.objects.create_superuser(
            email="boss@example.com", username="boss", password=VALID_PASSWORD
        )

        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_email_verified)
        self.assertIsNotNone(user.email_verified_at)
        self.assertTrue(Profile.objects.filter(pk=user.pk).exists())

    def test_get_by_natural_key_is_case_insensitive(self) -> None:
        user = create_user(email="natural@example.com", username="natural")

        self.assertEqual(User.objects.get_by_natural_key("NATURAL@example.com"), user)

    def test_str_returns_username_not_email(self) -> None:
        user = create_user(username="sourdough", email="secret@example.com")

        self.assertEqual(str(user), "sourdough")
