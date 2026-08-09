"""The visibility matrix.

This is the enforcement mechanism for the whole permission model, so it walks
the full cartesian product rather than spot-checking: every status × visibility
combination, seen by every class of viewer, through both the list and the detail
endpoint.

If a future change makes drafts listable or private recipes readable, this fails
loudly. Nothing else in the design would catch it.
"""

from __future__ import annotations

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.recipes.constants import RecipeScope, RecipeStatus, RecipeVisibility
from apps.recipes.tests.factories import create_recipe
from apps.users.tests.factories import create_user

STATUSES = (RecipeStatus.DRAFT, RecipeStatus.PUBLISHED, RecipeStatus.ARCHIVED)
VISIBILITIES = (
    RecipeVisibility.PUBLIC,
    RecipeVisibility.UNLISTED,
    RecipeVisibility.PRIVATE,
)

# (status, visibility) -> whether a stranger may open the detail page.
# Only a published + (public | unlisted) recipe is reachable by a stranger.
STRANGER_CAN_OPEN = {
    (RecipeStatus.PUBLISHED, RecipeVisibility.PUBLIC),
    (RecipeStatus.PUBLISHED, RecipeVisibility.UNLISTED),
}

# Only published + public appears in a public listing. Unlisted is excluded on
# purpose: absence from discovery is the entire point of unlisted.
APPEARS_IN_PUBLIC_LIST = {(RecipeStatus.PUBLISHED, RecipeVisibility.PUBLIC)}


class VisibilityMatrixTests(TestCase):
    """Every status × visibility × viewer combination, both endpoints."""

    @classmethod
    def setUpTestData(cls) -> None:
        cls.owner = create_user(username="owner")
        cls.stranger = create_user(username="stranger")
        cls.staff = create_user(username="staffer", is_staff=True)

        cls.recipes = {}
        for status in STATUSES:
            for visibility in VISIBILITIES:
                cls.recipes[(status, visibility)] = create_recipe(
                    author=cls.owner,
                    slug=f"{status}-{visibility}",
                    status=status,
                    visibility=visibility,
                )

    def _detail_status(self, *, slug: str, user=None) -> int:
        client = APIClient()
        if user is not None:
            client.force_login(user)
        return client.get(reverse("recipes:detail", kwargs={"slug": slug})).status_code

    def _list_slugs(self, *, user=None, scope: str | None = None) -> set[str]:
        client = APIClient()
        if user is not None:
            client.force_login(user)
        params = {"scope": scope} if scope else {}
        response = client.get(reverse("recipes:list"), params)
        self.assertEqual(response.status_code, 200)
        return {item["slug"] for item in response.json()["results"]}

    def test_anonymous_detail_access(self) -> None:
        for key, recipe in self.recipes.items():
            with self.subTest(state=key):
                expected = 200 if key in STRANGER_CAN_OPEN else 404
                self.assertEqual(self._detail_status(slug=recipe.slug), expected)

    def test_authenticated_stranger_detail_access(self) -> None:
        for key, recipe in self.recipes.items():
            with self.subTest(state=key):
                expected = 200 if key in STRANGER_CAN_OPEN else 404
                self.assertEqual(
                    self._detail_status(slug=recipe.slug, user=self.stranger), expected
                )

    def test_owner_can_always_open_own_recipe(self) -> None:
        for key, recipe in self.recipes.items():
            with self.subTest(state=key):
                self.assertEqual(
                    self._detail_status(slug=recipe.slug, user=self.owner), 200
                )

    def test_staff_can_always_open_any_recipe(self) -> None:
        for key, recipe in self.recipes.items():
            with self.subTest(state=key):
                self.assertEqual(
                    self._detail_status(slug=recipe.slug, user=self.staff), 200
                )

    def test_anonymous_list_shows_only_published_public(self) -> None:
        visible = self._list_slugs()

        for key, recipe in self.recipes.items():
            with self.subTest(state=key):
                if key in APPEARS_IN_PUBLIC_LIST:
                    self.assertIn(recipe.slug, visible)
                else:
                    self.assertNotIn(recipe.slug, visible)

    def test_stranger_list_shows_only_published_public(self) -> None:
        visible = self._list_slugs(user=self.stranger)

        for key, recipe in self.recipes.items():
            with self.subTest(state=key):
                if key in APPEARS_IN_PUBLIC_LIST:
                    self.assertIn(recipe.slug, visible)
                else:
                    self.assertNotIn(recipe.slug, visible)

    def test_owner_default_list_does_not_include_own_drafts(self) -> None:
        # The browse feed is not a personal workspace; drafts need scope=mine.
        visible = self._list_slugs(user=self.owner)

        self.assertNotIn(
            self.recipes[(RecipeStatus.DRAFT, RecipeVisibility.PUBLIC)].slug, visible
        )

    def test_scope_mine_shows_every_own_recipe(self) -> None:
        visible = self._list_slugs(user=self.owner, scope=RecipeScope.MINE)

        for key, recipe in self.recipes.items():
            with self.subTest(state=key):
                self.assertIn(recipe.slug, visible)

    def test_scope_mine_never_leaks_another_author(self) -> None:
        create_recipe(author=self.stranger, slug="stranger-draft")

        visible = self._list_slugs(user=self.owner, scope=RecipeScope.MINE)

        self.assertNotIn("stranger-draft", visible)

    def test_scope_mine_requires_authentication(self) -> None:
        response = APIClient().get(
            reverse("recipes:list"), {"scope": RecipeScope.MINE}
        )

        self.assertEqual(response.status_code, 401)

    def test_scope_all_is_narrowed_for_non_staff(self) -> None:
        # Silently narrowed rather than rejected: an error would confirm that
        # more recipes exist.
        visible = self._list_slugs(user=self.stranger, scope=RecipeScope.ALL)

        for key, recipe in self.recipes.items():
            if key not in APPEARS_IN_PUBLIC_LIST:
                self.assertNotIn(recipe.slug, visible)

    def test_scope_all_shows_everything_to_staff(self) -> None:
        visible = self._list_slugs(user=self.staff, scope=RecipeScope.ALL)

        for key, recipe in self.recipes.items():
            with self.subTest(state=key):
                self.assertIn(recipe.slug, visible)

    def test_unlisted_is_reachable_but_undiscoverable(self) -> None:
        recipe = self.recipes[(RecipeStatus.PUBLISHED, RecipeVisibility.UNLISTED)]

        self.assertEqual(self._detail_status(slug=recipe.slug), 200)
        self.assertNotIn(recipe.slug, self._list_slugs())

    def test_unlisted_never_appears_in_search(self) -> None:
        recipe = self.recipes[(RecipeStatus.PUBLISHED, RecipeVisibility.UNLISTED)]

        response = APIClient().get(reverse("recipes:search"), {"q": recipe.title})

        self.assertEqual(response.status_code, 200)
        self.assertNotIn(
            recipe.slug, {item["slug"] for item in response.json()["results"]}
        )

    def test_hidden_recipe_returns_404_not_403(self) -> None:
        # 403 would confirm the slug exists.
        recipe = self.recipes[(RecipeStatus.PUBLISHED, RecipeVisibility.PRIVATE)]
        client = APIClient()
        client.force_login(self.stranger)

        response = client.get(reverse("recipes:detail", kwargs={"slug": recipe.slug}))

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "not_found")

    def test_unknown_slug_is_indistinguishable_from_hidden(self) -> None:
        hidden = self.recipes[(RecipeStatus.PUBLISHED, RecipeVisibility.PRIVATE)]
        client = APIClient()
        client.force_login(self.stranger)

        hidden_response = client.get(
            reverse("recipes:detail", kwargs={"slug": hidden.slug})
        )
        missing_response = client.get(
            reverse("recipes:detail", kwargs={"slug": "no-such-recipe"})
        )

        self.assertEqual(hidden_response.status_code, missing_response.status_code)
        for field in ("code", "message"):
            self.assertEqual(
                hidden_response.json()["error"][field],
                missing_response.json()["error"][field],
            )
