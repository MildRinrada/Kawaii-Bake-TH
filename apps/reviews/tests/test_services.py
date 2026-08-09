"""Service-level tests: creation rules, duplicates, moderation, soft delete."""

from __future__ import annotations

from decimal import Decimal

from django.test import TestCase

from apps.recipes.tests.factories import create_published_recipe
from apps.reviews.constants import ReviewStatus, ReviewTargetKind
from apps.reviews.exceptions import (
    AlreadyReviewedError,
    ModerationNotAllowedError,
    OwnContentReviewError,
    ReviewNotFoundError,
    ReviewTargetNotFoundError,
)
from apps.reviews.models import Review
from apps.reviews.selectors import rating_selector
from apps.reviews.services import review_service
from apps.reviews.tests.factories import create_review
from apps.users.tests.factories import create_user


class CreateReviewTests(TestCase):
    """Who may review what, exactly once while active."""

    def setUp(self) -> None:
        self.author = create_user(username="rvauthor")
        self.reviewer = create_user(username="rvreviewer")
        self.recipe = create_published_recipe(author=self.author, slug="rv-bread")

    def _create(self, **overrides) -> Review:
        data = {"rating": 5, "comment": "อร่อยมาก"}
        data.update(overrides.pop("data", {}))
        return review_service.create_review(
            user_id=overrides.pop("user_id", self.reviewer.id),
            kind=ReviewTargetKind.RECIPE,
            slug=overrides.pop("slug", "rv-bread"),
            data=data,
        )

    def test_review_is_created_active_with_reviewer_loaded(self) -> None:
        review = self._create()
        self.assertEqual(review.status, ReviewStatus.ACTIVE)
        self.assertEqual(review.rating, 5)
        self.assertEqual(review.recipe_id, self.recipe.pk)
        self.assertEqual(review.user.username, "rvreviewer")

    def test_own_content_cannot_be_reviewed(self) -> None:
        with self.assertRaises(OwnContentReviewError):
            self._create(user_id=self.author.id)

    def test_hidden_target_is_the_same_404(self) -> None:
        with self.assertRaises(ReviewTargetNotFoundError):
            self._create(slug="no-such-recipe")

    def test_duplicate_active_review_is_409(self) -> None:
        self._create()
        with self.assertRaises(AlreadyReviewedError):
            self._create(data={"rating": 1})

    def test_soft_delete_frees_the_slot(self) -> None:
        review = self._create()
        review_service.delete_review(review_id=review.pk, viewer_id=self.reviewer.id)

        # The row survives as history…
        row = Review.objects.get(pk=review.pk)
        self.assertEqual(row.status, ReviewStatus.DELETED)

        # …and a fresh review is allowed.
        second = self._create(data={"rating": 3})
        self.assertNotEqual(second.pk, review.pk)

    def test_whitespace_comment_normalizes_to_empty(self) -> None:
        review = self._create(data={"comment": "   \n  "})
        self.assertEqual(review.comment, "")


class ModerationTests(TestCase):
    """Owners edit; staff moderate; deleted is gone for everyone."""

    def setUp(self) -> None:
        self.author = create_user(username="rmauthor")
        self.reviewer = create_user(username="rmreviewer")
        self.staff = create_user(username="rmstaff", is_staff=True)
        self.recipe = create_published_recipe(author=self.author, slug="rm-cake")
        self.review = create_review(user=self.reviewer, recipe=self.recipe)

    def test_owner_edits_rating_and_comment(self) -> None:
        updated = review_service.update_review(
            review_id=self.review.pk,
            viewer_id=self.reviewer.id,
            data={"rating": 2, "comment": "แก้ไขความเห็น"},
        )
        self.assertEqual(updated.rating, 2)
        self.assertEqual(updated.comment, "แก้ไขความเห็น")

    def test_owner_cannot_moderate(self) -> None:
        with self.assertRaises(ModerationNotAllowedError):
            review_service.update_review(
                review_id=self.review.pk,
                viewer_id=self.reviewer.id,
                data={"status": ReviewStatus.HIDDEN},
            )

    def test_staff_hides_and_restores(self) -> None:
        hidden = review_service.update_review(
            review_id=self.review.pk,
            viewer_id=self.staff.id,
            viewer_is_staff=True,
            data={"status": ReviewStatus.HIDDEN},
        )
        self.assertEqual(hidden.status, ReviewStatus.HIDDEN)

        restored = review_service.update_review(
            review_id=self.review.pk,
            viewer_id=self.staff.id,
            viewer_is_staff=True,
            data={"status": ReviewStatus.ACTIVE},
        )
        self.assertEqual(restored.status, ReviewStatus.ACTIVE)

    def test_someone_elses_review_is_the_same_404(self) -> None:
        other = create_user(username="rmother")
        with self.assertRaises(ReviewNotFoundError):
            review_service.update_review(
                review_id=self.review.pk, viewer_id=other.id, data={"rating": 1}
            )

    def test_deleted_review_is_unaddressable_even_by_staff(self) -> None:
        review_service.delete_review(
            review_id=self.review.pk, viewer_id=self.reviewer.id
        )
        with self.assertRaises(ReviewNotFoundError):
            review_service.update_review(
                review_id=self.review.pk,
                viewer_id=self.staff.id,
                viewer_is_staff=True,
                data={"rating": 1},
            )


class RatingStatisticsTests(TestCase):
    """Statistics are computed over ACTIVE rows only — never stored."""

    def setUp(self) -> None:
        self.author = create_user(username="rsauthor")
        self.recipe = create_published_recipe(author=self.author, slug="rs-pie")

    def test_summary_averages_counts_and_distributes(self) -> None:
        for index, rating in enumerate((5, 4, 4, 1)):
            create_review(
                user=create_user(username=f"rsuser{index}"),
                recipe=self.recipe,
                rating=rating,
            )
        hidden_user = create_user(username="rshidden")
        create_review(
            user=hidden_user, recipe=self.recipe, rating=1, status=ReviewStatus.HIDDEN
        )

        summary = rating_selector.for_recipe(recipe_id=self.recipe.pk)

        self.assertEqual(summary.count, 4)
        self.assertEqual(summary.average, Decimal("3.50"))
        self.assertEqual(summary.distribution, {1: 1, 2: 0, 3: 0, 4: 2, 5: 1})

    def test_empty_summary_has_null_average(self) -> None:
        summary = rating_selector.for_recipe(recipe_id=self.recipe.pk)
        self.assertIsNone(summary.average)
        self.assertEqual(summary.count, 0)
