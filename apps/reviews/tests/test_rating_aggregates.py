"""Course rating aggregates pushed through the review choke point (ADR 0021)."""

from __future__ import annotations

from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.courses.constants import CourseStatus
from apps.courses.models import Course
from apps.courses.tests.factories import create_course
from apps.reviews.constants import ReviewStatus, ReviewTargetKind
from apps.reviews.services import review_service
from apps.reviews.tests.factories import create_review
from apps.users.tests.factories import create_user


class CourseRatingAggregateTests(TestCase):
    """Every review mutation keeps the stored course aggregate true."""

    def setUp(self) -> None:
        self.instructor = create_user(email="t@example.com", username="teacher")
        self.course = create_course(
            instructor=self.instructor,
            status=CourseStatus.PUBLISHED,
            published_at=timezone.now(),
        )
        self.fan = create_user(email="fan@example.com", username="fanone")
        self.fan_two = create_user(email="fan2@example.com", username="fantwo")

    def _aggregate(self) -> tuple[Decimal | None, int]:
        course = Course.objects.get(pk=self.course.pk)
        return course.rating_average, course.rating_count

    def _review(self, user, rating: int):
        return review_service.create_review(
            user_id=user.pk,
            kind=ReviewTargetKind.COURSE,
            slug=self.course.slug,
            data={"rating": rating},
        )

    def test_create_review_sets_aggregate(self) -> None:
        self._review(self.fan, 5)

        self.assertEqual(self._aggregate(), (Decimal("5.00"), 1))

    def test_second_review_averages(self) -> None:
        self._review(self.fan, 5)
        self._review(self.fan_two, 4)

        self.assertEqual(self._aggregate(), (Decimal("4.50"), 2))

    def test_editing_a_rating_recomputes(self) -> None:
        review = self._review(self.fan, 5)

        review_service.update_review(
            review_id=review.pk, viewer_id=self.fan.pk, data={"rating": 3}
        )

        self.assertEqual(self._aggregate(), (Decimal("3.00"), 1))

    def test_hiding_a_review_excludes_it(self) -> None:
        review = self._review(self.fan, 5)
        self._review(self.fan_two, 3)
        staff = create_user(
            email="mod@example.com", username="moderator", is_staff=True
        )

        review_service.update_review(
            review_id=review.pk,
            viewer_id=staff.pk,
            viewer_is_staff=True,
            data={"status": ReviewStatus.HIDDEN},
        )

        self.assertEqual(self._aggregate(), (Decimal("3.00"), 1))

    def test_deleting_the_last_review_resets_to_null(self) -> None:
        review = self._review(self.fan, 5)

        review_service.delete_review(review_id=review.pk, viewer_id=self.fan.pk)

        self.assertEqual(self._aggregate(), (None, 0))

    def test_recipe_reviews_do_not_touch_course_aggregates(self) -> None:
        from apps.recipes.constants import RecipeStatus
        from apps.recipes.tests.factories import create_recipe

        recipe = create_recipe(
            author=self.instructor,
            status=RecipeStatus.PUBLISHED,
            published_at=timezone.now(),
        )
        review_service.create_review(
            user_id=self.fan.pk,
            kind=ReviewTargetKind.RECIPE,
            slug=recipe.slug,
            data={"rating": 5},
        )

        self.assertEqual(self._aggregate(), (None, 0))

    def test_rebuild_command_repairs_drift(self) -> None:
        # The factory writes at the model layer — deliberately bypassing
        # the choke point, exactly the drift the command exists to repair.
        create_review(user=self.fan, course=self.course, rating=4)
        self.assertEqual(self._aggregate(), (None, 0))

        call_command("rebuild_rating_aggregates")

        self.assertEqual(self._aggregate(), (Decimal("4.00"), 1))
