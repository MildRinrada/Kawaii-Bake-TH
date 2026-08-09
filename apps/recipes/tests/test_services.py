"""Tests for the recipe service and repository layers."""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.recipes.constants import RecipeStatus, RecipeVisibility
from apps.recipes.exceptions import (
    InvalidCategoryError,
    RecipeNotPublishableError,
    RecipeNotVisibleError,
    SlugImmutableError,
)
from apps.recipes.models import Recipe, RecipeIngredient, RecipeStep
from apps.recipes.services import publish_service, recipe_service
from apps.recipes.tests.factories import (
    THAI_TITLE,
    create_category,
    create_published_recipe,
    create_recipe,
    make_publishable,
)
from apps.users.tests.factories import create_user


class RecipeCreateServiceTests(TestCase):
    """Creating recipes."""

    def setUp(self) -> None:
        self.user = create_user()
        self.category = create_category(slug="cake")

    def _payload(self, **overrides) -> dict:
        payload = {
            "title": "Chocolate Brownie",
            "summary": "Fudgy and rich.",
            "prep_minutes": 15,
            "cook_minutes": 30,
            "servings": 8,
            "category_slugs": ["cake"],
            "ingredients": [{"name": "Butter", "quantity": 200, "unit": "g"}],
            "steps": [{"body": "Melt the butter."}],
        }
        payload.update(overrides)
        return payload

    def test_create_stores_recipe_with_children(self) -> None:
        recipe = recipe_service.create_recipe(
            author_id=self.user.id, data=self._payload()
        )

        self.assertEqual(recipe.title, "Chocolate Brownie")
        self.assertEqual(recipe.status, RecipeStatus.DRAFT)
        self.assertEqual(recipe.total_minutes, 45)
        self.assertEqual(recipe.ingredients.count(), 1)
        self.assertEqual(recipe.steps.count(), 1)
        self.assertEqual(recipe.categories.count(), 1)

    def test_slug_is_generated_from_the_title(self) -> None:
        recipe = recipe_service.create_recipe(
            author_id=self.user.id, data=self._payload()
        )

        self.assertEqual(recipe.slug, "chocolate-brownie")

    def test_thai_title_produces_a_thai_slug(self) -> None:
        recipe = recipe_service.create_recipe(
            author_id=self.user.id, data=self._payload(title=THAI_TITLE)
        )

        self.assertNotEqual(recipe.slug, "")
        self.assertFalse(recipe.slug.startswith("recipe-"))
        self.assertTrue(any("฀" <= char <= "๿" for char in recipe.slug))

    def test_duplicate_title_gets_a_distinct_slug(self) -> None:
        first = recipe_service.create_recipe(
            author_id=self.user.id, data=self._payload()
        )
        second = recipe_service.create_recipe(
            author_id=self.user.id, data=self._payload()
        )

        self.assertNotEqual(first.slug, second.slug)
        self.assertTrue(second.slug.startswith("chocolate-brownie-"))

    def test_positions_are_assigned_from_array_order(self) -> None:
        recipe = recipe_service.create_recipe(
            author_id=self.user.id,
            data=self._payload(
                steps=[{"body": "First."}, {"body": "Second."}, {"body": "Third."}]
            ),
        )

        bodies = list(recipe.steps.order_by("position").values_list("body", flat=True))
        self.assertEqual(bodies, ["First.", "Second.", "Third."])

    def test_unknown_category_is_rejected(self) -> None:
        with self.assertRaises(InvalidCategoryError) as ctx:
            recipe_service.create_recipe(
                author_id=self.user.id, data=self._payload(category_slugs=["nope"])
            )

        self.assertEqual(ctx.exception.details["category_slugs"], ["nope"])

    def test_negative_time_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            recipe_service.create_recipe(
                author_id=self.user.id, data=self._payload(cook_minutes=-5)
            )

    def test_implausible_total_time_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            recipe_service.create_recipe(
                author_id=self.user.id,
                data=self._payload(prep_minutes=999_999, cook_minutes=1),
            )

    def test_invalid_servings_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            recipe_service.create_recipe(
                author_id=self.user.id, data=self._payload(servings=0)
            )

    def test_duplicate_ingredient_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            recipe_service.create_recipe(
                author_id=self.user.id,
                data=self._payload(
                    ingredients=[
                        {"name": "Butter", "quantity": 1, "unit": "g"},
                        {"name": "  BUTTER ", "quantity": 2, "unit": "g"},
                    ]
                ),
            )

    def test_non_positive_quantity_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            recipe_service.create_recipe(
                author_id=self.user.id,
                data=self._payload(ingredients=[{"name": "Salt", "quantity": 0}]),
            )

    def test_blank_step_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            recipe_service.create_recipe(
                author_id=self.user.id, data=self._payload(steps=[{"body": "   "}])
            )

    def test_draft_may_be_created_without_ingredients_or_steps(self) -> None:
        # Completeness is a publish-time rule; drafts must be saveable.
        recipe = recipe_service.create_recipe(
            author_id=self.user.id,
            data=self._payload(ingredients=[], steps=[], category_slugs=[]),
        )

        self.assertEqual(recipe.status, RecipeStatus.DRAFT)

    def test_failed_creation_leaves_nothing_behind(self) -> None:
        with self.assertRaises(ValidationError):
            recipe_service.create_recipe(
                author_id=self.user.id, data=self._payload(steps=[{"body": ""}])
            )

        self.assertEqual(Recipe.objects.count(), 0)


class RecipeUpdateServiceTests(TestCase):
    """Updating recipes."""

    def setUp(self) -> None:
        self.user = create_user()
        self.other = create_user()
        self.recipe = create_recipe(author=self.user, slug="brownie")

    def test_partial_update_leaves_other_fields_alone(self) -> None:
        original = self.recipe.title

        updated = recipe_service.update_recipe(
            slug="brownie", viewer_id=self.user.id, data={"summary": "New summary."}
        )

        self.assertEqual(updated.summary, "New summary.")
        self.assertEqual(updated.title, original)

    def test_supplying_steps_replaces_them_entirely(self) -> None:
        recipe_service.update_recipe(
            slug="brownie",
            viewer_id=self.user.id,
            data={"steps": [{"body": "One."}, {"body": "Two."}]},
        )

        recipe_service.update_recipe(
            slug="brownie", viewer_id=self.user.id, data={"steps": [{"body": "Only."}]}
        )

        self.assertEqual(RecipeStep.objects.filter(recipe=self.recipe).count(), 1)

    def test_omitting_steps_leaves_them_untouched(self) -> None:
        recipe_service.update_recipe(
            slug="brownie", viewer_id=self.user.id, data={"steps": [{"body": "One."}]}
        )

        recipe_service.update_recipe(
            slug="brownie", viewer_id=self.user.id, data={"title": "Renamed brownie"}
        )

        self.assertEqual(RecipeStep.objects.filter(recipe=self.recipe).count(), 1)

    def test_reordering_is_expressed_by_array_order(self) -> None:
        recipe_service.update_recipe(
            slug="brownie",
            viewer_id=self.user.id,
            data={"steps": [{"body": "A"}, {"body": "B"}]},
        )

        recipe_service.update_recipe(
            slug="brownie",
            viewer_id=self.user.id,
            data={"steps": [{"body": "B"}, {"body": "A"}]},
        )

        bodies = list(
            RecipeStep.objects.filter(recipe=self.recipe)
            .order_by("position")
            .values_list("body", flat=True)
        )
        self.assertEqual(bodies, ["B", "A"])

    def test_stranger_cannot_update(self) -> None:
        with self.assertRaises(RecipeNotVisibleError):
            recipe_service.update_recipe(
                slug="brownie", viewer_id=self.other.id, data={"title": "Hijacked"}
            )

    def test_staff_can_update_another_users_recipe(self) -> None:
        staff = create_user(is_staff=True)

        updated = recipe_service.update_recipe(
            slug="brownie",
            viewer_id=staff.id,
            viewer_is_staff=True,
            data={"summary": "Moderated."},
        )

        self.assertEqual(updated.summary, "Moderated.")

    def test_slug_is_mutable_before_publication(self) -> None:
        updated = recipe_service.update_recipe(
            slug="brownie", viewer_id=self.user.id, data={"slug": "fudgy-brownie"}
        )

        self.assertEqual(updated.slug, "fudgy-brownie")

    def test_slug_is_frozen_after_publication(self) -> None:
        published = create_published_recipe(author=self.user, slug="published-cake")

        with self.assertRaises(SlugImmutableError):
            recipe_service.update_recipe(
                slug=published.slug, viewer_id=self.user.id, data={"slug": "new-cake"}
            )

    def test_visibility_is_editable_but_status_is_not(self) -> None:
        updated = recipe_service.update_recipe(
            slug="brownie",
            viewer_id=self.user.id,
            data={"visibility": RecipeVisibility.PRIVATE, "status": "published"},
        )

        self.assertEqual(updated.visibility, RecipeVisibility.PRIVATE)
        # `status` is not in RECIPE_EDITABLE_FIELDS, so publishing cannot be
        # routed around the completeness checks.
        self.assertEqual(updated.status, RecipeStatus.DRAFT)


class RecipeDeleteServiceTests(TestCase):
    """Deleting recipes."""

    def setUp(self) -> None:
        self.user = create_user()
        self.other = create_user()

    def test_owner_can_delete(self) -> None:
        create_recipe(author=self.user, slug="doomed")

        recipe_service.delete_recipe(slug="doomed", viewer_id=self.user.id)

        self.assertFalse(Recipe.objects.filter(slug="doomed").exists())

    def test_stranger_cannot_delete(self) -> None:
        create_recipe(author=self.user, slug="safe")

        with self.assertRaises(RecipeNotVisibleError):
            recipe_service.delete_recipe(slug="safe", viewer_id=self.other.id)

        self.assertTrue(Recipe.objects.filter(slug="safe").exists())

    def test_deleting_removes_children(self) -> None:
        recipe = create_recipe(
            author=self.user, slug="doomed", with_ingredients=True, with_steps=True
        )
        recipe_id = recipe.pk

        recipe_service.delete_recipe(slug="doomed", viewer_id=self.user.id)

        self.assertFalse(RecipeIngredient.objects.filter(recipe_id=recipe_id).exists())
        self.assertFalse(RecipeStep.objects.filter(recipe_id=recipe_id).exists())


class PublishServiceTests(TestCase):
    """The lifecycle state machine."""

    def setUp(self) -> None:
        self.user = create_user()
        self.recipe = create_recipe(author=self.user, slug="cake")

    def test_publishing_an_incomplete_recipe_reports_every_problem(self) -> None:
        with self.assertRaises(RecipeNotPublishableError) as ctx:
            publish_service.publish(slug="cake", viewer_id=self.user.id)

        details = ctx.exception.details
        self.assertIn("ingredients", details)
        self.assertIn("steps", details)
        self.assertIn("category_slugs", details)
        self.assertIn("cover_image", details)

    def test_publishing_a_complete_recipe_succeeds(self) -> None:
        make_publishable(self.recipe)

        published = publish_service.publish(slug="cake", viewer_id=self.user.id)

        self.assertEqual(published.status, RecipeStatus.PUBLISHED)
        self.assertIsNotNone(published.published_at)

    def test_publishing_is_idempotent(self) -> None:
        make_publishable(self.recipe)
        first = publish_service.publish(slug="cake", viewer_id=self.user.id)
        stamp = first.published_at

        second = publish_service.publish(slug="cake", viewer_id=self.user.id)

        self.assertEqual(second.published_at, stamp)

    def test_unpublish_returns_to_draft_and_keeps_the_date(self) -> None:
        make_publishable(self.recipe)
        publish_service.publish(slug="cake", viewer_id=self.user.id)
        self.recipe.refresh_from_db()
        stamp = self.recipe.published_at

        publish_service.unpublish(slug="cake", viewer_id=self.user.id)

        self.recipe.refresh_from_db()
        self.assertEqual(self.recipe.status, RecipeStatus.DRAFT)
        self.assertEqual(self.recipe.published_at, stamp)

    def test_republish_does_not_move_the_original_date(self) -> None:
        make_publishable(self.recipe)
        publish_service.publish(slug="cake", viewer_id=self.user.id)
        self.recipe.refresh_from_db()
        stamp = self.recipe.published_at

        publish_service.unpublish(slug="cake", viewer_id=self.user.id)
        republished = publish_service.publish(slug="cake", viewer_id=self.user.id)

        self.assertEqual(republished.published_at, stamp)

    def test_archive_and_restore_are_reversible(self) -> None:
        make_publishable(self.recipe)
        publish_service.publish(slug="cake", viewer_id=self.user.id)

        publish_service.archive(slug="cake", viewer_id=self.user.id)
        self.recipe.refresh_from_db()
        self.assertEqual(self.recipe.status, RecipeStatus.ARCHIVED)

        publish_service.publish(slug="cake", viewer_id=self.user.id)
        self.recipe.refresh_from_db()
        self.assertEqual(self.recipe.status, RecipeStatus.PUBLISHED)

    def test_archived_recipe_is_revalidated_on_republish(self) -> None:
        make_publishable(self.recipe)
        publish_service.publish(slug="cake", viewer_id=self.user.id)
        publish_service.archive(slug="cake", viewer_id=self.user.id)
        self.recipe.steps.all().delete()

        with self.assertRaises(RecipeNotPublishableError):
            publish_service.publish(slug="cake", viewer_id=self.user.id)

    def test_stranger_cannot_change_status(self) -> None:
        stranger = create_user()
        make_publishable(self.recipe)

        with self.assertRaises(RecipeNotVisibleError):
            publish_service.publish(slug="cake", viewer_id=stranger.id)
