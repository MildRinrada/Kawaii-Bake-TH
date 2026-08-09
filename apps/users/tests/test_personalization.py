"""Phase 14: taxonomy-backed categories, the fact, completion, settings."""

from __future__ import annotations

from django.test import TestCase
from rest_framework.test import APIClient

from apps.assistant.constants import AssistantLanguage
from apps.recipes.tests.factories import create_category
from apps.users.constants import PreferredLanguage
from apps.users.selectors import profile_selector
from apps.users.services import profile_service
from apps.users.tests.factories import create_user

PROFILE_URL = "/api/v1/users/profile/"
PROFILE_UPDATE_URL = "/api/v1/users/profile/update/"
SETTINGS_URL = "/api/v1/me/settings/"


class FavoriteCategoryTaxonomyTests(TestCase):
    """Favourite categories are real taxonomy relations since Phase 14."""

    def setUp(self) -> None:
        self.client = APIClient()
        self.user = create_user(username="p14cats")
        self.bread = create_category(slug="bread")
        self.cake = create_category(slug="cake")

    def test_patch_round_trips_slugs_through_the_taxonomy(self) -> None:
        self.client.force_login(self.user)
        response = self.client.patch(
            PROFILE_UPDATE_URL,
            {"favorite_categories": ["cake", "bread", "cake"]},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["favorite_categories"], ["bread", "cake"]
        )

    def test_admin_added_category_is_selectable_without_code_change(self) -> None:
        create_category(slug="croissant-lab")
        self.client.force_login(self.user)
        response = self.client.patch(
            PROFILE_UPDATE_URL,
            {"favorite_categories": ["croissant-lab"]},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["favorite_categories"], ["croissant-lab"]
        )

    def test_unknown_slug_is_rejected_and_nothing_persists(self) -> None:
        self.client.force_login(self.user)
        response = self.client.patch(
            PROFILE_UPDATE_URL,
            {"favorite_categories": ["bread", "no-such-category"]},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        profile = profile_service.get_own_profile(user_id=self.user.id)
        self.assertEqual(list(profile.favorite_categories.all()), [])

    def test_set_is_idempotent(self) -> None:
        for _ in range(2):
            profile_service.update_profile(
                user_id=self.user.id,
                changes={"favorite_categories": ["bread", "cake"]},
            )
        profile = profile_service.get_own_profile(user_id=self.user.id)
        self.assertEqual(profile.favorite_categories.count(), 2)

    def test_deleted_category_leaves_the_list_by_cascade(self) -> None:
        profile_service.update_profile(
            user_id=self.user.id, changes={"favorite_categories": ["bread"]}
        )
        self.bread.delete()
        profile = profile_service.get_own_profile(user_id=self.user.id)
        self.assertEqual(list(profile.favorite_categories.all()), [])

    def test_own_profile_read_is_two_queries(self) -> None:
        profile_service.update_profile(
            user_id=self.user.id,
            changes={"favorite_categories": ["bread", "cake"]},
        )
        with self.assertNumQueries(2):
            profile = profile_selector.get_profile(user_id=self.user.id)
            list(profile.favorite_categories.all())


class PersonalizationFactTests(TestCase):
    """The users-owned fact: explicit only, language included, bounded."""

    def setUp(self) -> None:
        self.user = create_user(username="p14fact")
        self.bread = create_category(slug="bread")

    def test_fact_shape_and_defaults(self) -> None:
        fact = profile_selector.get_personalization_fact(user_id=self.user.id)
        self.assertEqual(fact.experience_level, "beginner")
        self.assertEqual(fact.favorite_category_slugs, ())
        self.assertEqual(fact.preferred_language, PreferredLanguage.TH)

    def test_fact_reflects_explicit_choices(self) -> None:
        profile_service.update_profile(
            user_id=self.user.id, changes={"favorite_categories": ["bread"]}
        )
        profile_service.update_preference(
            user_id=self.user.id, changes={"locale": "en"}
        )
        fact = profile_selector.get_personalization_fact(user_id=self.user.id)
        self.assertEqual(fact.favorite_category_slugs, ("bread",))
        self.assertEqual(fact.preferred_language, "en")

    def test_fact_is_two_queries(self) -> None:
        with self.assertNumQueries(2):
            profile_selector.get_personalization_fact(user_id=self.user.id)

    def test_language_codes_match_the_assistant(self) -> None:
        # The compatibility pin (ADR 0020 §8): one language vocabulary,
        # no translation glue between users and assistant.
        self.assertEqual(
            set(PreferredLanguage.values), set(AssistantLanguage.values)
        )

    def test_fact_carries_no_behavioral_or_private_fields(self) -> None:
        fact = profile_selector.get_personalization_fact(user_id=self.user.id)
        self.assertEqual(
            sorted(fact.__dataclass_fields__),
            ["experience_level", "favorite_category_slugs", "preferred_language"],
        )


class ProfileCompletionTests(TestCase):
    """Completion is derived, deterministic, and never stored."""

    def setUp(self) -> None:
        self.user = create_user(username="p14done")
        create_category(slug="bread")

    def completion(self):
        profile = profile_selector.get_profile(user_id=self.user.id)
        return profile_selector.profile_completion(profile)

    def test_empty_profile(self) -> None:
        result = self.completion()
        self.assertEqual((result.completed, result.total, result.percent), (0, 6, 0))
        self.assertIn("bio", result.missing)
        self.assertNotIn("experience_level", result.missing)

    def test_partial_profile(self) -> None:
        profile_service.update_profile(
            user_id=self.user.id,
            changes={"display_name": "มายด์", "bio": "ชอบอบขนมปัง 🍞"},
        )
        result = self.completion()
        self.assertEqual(result.completed, 2)
        self.assertEqual(result.percent, 33)

    def test_categories_count_toward_completion(self) -> None:
        profile_service.update_profile(
            user_id=self.user.id, changes={"favorite_categories": ["bread"]}
        )
        result = self.completion()
        self.assertNotIn("favorite_categories", result.missing)

    def test_deterministic(self) -> None:
        self.assertEqual(self.completion(), self.completion())


class SettingsCompositionTests(TestCase):
    """/me/settings/ reads across owners and writes nothing."""

    def setUp(self) -> None:
        self.client = APIClient()
        self.user = create_user(username="p14set")
        create_category(slug="bread")

    def test_anonymous_is_rejected(self) -> None:
        self.assertIn(self.client.get(SETTINGS_URL).status_code, (401, 403))

    def test_composition_blocks(self) -> None:
        profile_service.update_profile(
            user_id=self.user.id,
            changes={"bio": "หลงรักเบเกอรี่", "favorite_categories": ["bread"]},
        )
        self.client.force_login(self.user)
        payload = self.client.get(SETTINGS_URL).json()

        self.assertEqual(
            sorted(payload),
            ["notifications", "preferences", "profile", "profile_completion"],
        )
        self.assertEqual(payload["profile"]["bio"], "หลงรักเบเกอรี่")
        self.assertEqual(payload["profile"]["favorite_categories"], ["bread"])
        self.assertEqual(payload["preferences"]["locale"], "th")
        # The notification block is the notifications app's own effective
        # view: every wired event, defaulting to enabled, no stored rows.
        self.assertTrue(payload["notifications"])
        self.assertTrue(all(payload["notifications"].values()))
        self.assertEqual(payload["profile_completion"]["completed"], 2)

    def test_settings_is_read_only(self) -> None:
        self.client.force_login(self.user)
        self.assertEqual(self.client.post(SETTINGS_URL, {}).status_code, 405)
        self.assertEqual(self.client.patch(SETTINGS_URL, {}).status_code, 405)

    def test_settings_service_query_count(self) -> None:
        self.client.force_login(self.user)
        self.client.get(SETTINGS_URL)  # warm session
        with self.assertNumQueries(6):
            self.client.get(SETTINGS_URL)


class PrivacyLeakTests(TestCase):
    """Private data stays out of every public projection."""

    def setUp(self) -> None:
        self.client = APIClient()
        self.owner = create_user(username="p14priv")
        profile_service.update_preference(
            user_id=self.owner.id,
            changes={"show_location": False, "show_birthday": False},
        )
        profile_service.update_profile(
            user_id=self.owner.id,
            changes={"location": "เชียงใหม่", "bio": "สวัสดี 🧁"},
        )

    def test_public_profile_hides_what_privacy_says(self) -> None:
        response = self.client.get("/api/v1/users/p14priv/")
        payload = response.json()
        self.assertIsNone(payload["location"])
        self.assertIsNone(payload["birthday"])
        self.assertEqual(payload["bio"], "สวัสดี 🧁")

    def test_public_profile_never_carries_account_or_preference_keys(self) -> None:
        raw = self.client.get("/api/v1/users/p14priv/").content.decode()
        for forbidden in ("email", "locale", "theme", "profile_visibility",
                          "email_marketing", "is_staff"):
            self.assertNotIn(forbidden, raw)

    def test_owner_still_sees_their_own_hidden_fields(self) -> None:
        self.client.force_login(self.owner)
        payload = self.client.get("/api/v1/users/p14priv/").json()
        self.assertEqual(payload["location"], "เชียงใหม่")
