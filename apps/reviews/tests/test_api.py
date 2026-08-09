"""API tests for reviews and rating statistics."""

from __future__ import annotations

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.courses.tests.factories import create_published_course
from apps.recipes.constants import RecipeVisibility
from apps.recipes.tests.factories import create_published_recipe, create_recipe
from apps.reviews.constants import ReviewStatus
from apps.reviews.tests.factories import create_review
from apps.users.tests.factories import create_user


class ReviewApiTests(TestCase):
    """The nested endpoints, permission split and status codes."""

    def setUp(self) -> None:
        self.client = APIClient()
        self.author = create_user(username="raauthor")
        self.reviewer = create_user(username="rareviewer")
        self.recipe = create_published_recipe(author=self.author, slug="ra-bread")
        self.course = create_published_course(instructor=self.author, slug="ra-course")

    def test_anonymous_reads_reviews_and_rating(self) -> None:
        create_review(user=self.reviewer, recipe=self.recipe, rating=5)
        listing = self.client.get(f"/api/v1/recipes/{self.recipe.slug}/reviews/")
        rating = self.client.get(f"/api/v1/recipes/{self.recipe.slug}/rating/")

        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.json()["count"], 1)
        self.assertEqual(rating.status_code, 200)
        self.assertEqual(rating.json()["average"], "5.00")

    def test_hidden_reviews_never_appear_in_the_listing(self) -> None:
        create_review(
            user=self.reviewer,
            recipe=self.recipe,
            status=ReviewStatus.HIDDEN,
        )
        listing = self.client.get(f"/api/v1/recipes/{self.recipe.slug}/reviews/")
        self.assertEqual(listing.json()["count"], 0)

    def test_anonymous_cannot_create(self) -> None:
        response = self.client.post(
            f"/api/v1/recipes/{self.recipe.slug}/reviews/", {"rating": 5}
        )
        self.assertEqual(response.status_code, 401)

    def test_course_review_roundtrip(self) -> None:
        self.client.force_login(self.reviewer)
        created = self.client.post(
            f"/api/v1/courses/{self.course.slug}/reviews/",
            {"rating": 4, "comment": "สอนดีมาก"},
            format="json",
        )
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.json()["target"], "course")

        rating = self.client.get(f"/api/v1/courses/{self.course.slug}/rating/")
        self.assertEqual(rating.json()["count"], 1)

    def test_duplicate_review_is_409(self) -> None:
        self.client.force_login(self.reviewer)
        self.client.post(
            f"/api/v1/recipes/{self.recipe.slug}/reviews/", {"rating": 5}, format="json"
        )
        second = self.client.post(
            f"/api/v1/recipes/{self.recipe.slug}/reviews/", {"rating": 1}, format="json"
        )
        self.assertEqual(second.status_code, 409)
        self.assertEqual(second.json()["error"]["code"], "already_reviewed")

    def test_own_content_review_is_400(self) -> None:
        self.client.force_login(self.author)
        response = self.client.post(
            f"/api/v1/recipes/{self.recipe.slug}/reviews/", {"rating": 5}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "own_content")

    def test_private_target_is_404_even_for_reviewing(self) -> None:
        create_recipe(
            author=self.author,
            slug="ra-secret",
            status="published",
            visibility=RecipeVisibility.PRIVATE,
        )
        self.client.force_login(self.reviewer)
        response = self.client.post(
            "/api/v1/recipes/ra-secret/reviews/", {"rating": 5}, format="json"
        )
        self.assertEqual(response.status_code, 404)

    def test_owner_patch_and_delete_and_admin_moderation(self) -> None:
        review = create_review(user=self.reviewer, recipe=self.recipe)
        self.client.force_login(self.reviewer)

        patched = self.client.patch(
            reverse("reviews:detail", args=[review.pk]),
            {"rating": 2},
            format="json",
        )
        self.assertEqual(patched.status_code, 200)
        self.assertEqual(patched.json()["rating"], 2)

        forbidden = self.client.patch(
            reverse("reviews:detail", args=[review.pk]),
            {"status": "hidden"},
            format="json",
        )
        self.assertEqual(forbidden.status_code, 403)

        staff = create_user(username="rastaff", is_staff=True)
        self.client.force_login(staff)
        moderated = self.client.patch(
            reverse("reviews:detail", args=[review.pk]),
            {"status": "hidden"},
            format="json",
        )
        self.assertEqual(moderated.status_code, 200)
        self.assertEqual(moderated.json()["status"], "hidden")

        self.client.force_login(self.reviewer)
        deleted = self.client.delete(reverse("reviews:detail", args=[review.pk]))
        self.assertEqual(deleted.status_code, 204)
        gone = self.client.patch(
            reverse("reviews:detail", args=[review.pk]), {"rating": 5}, format="json"
        )
        self.assertEqual(gone.status_code, 404)

    def test_review_listing_query_count_is_flat(self) -> None:
        for index in range(4):
            create_review(
                user=create_user(username=f"raq{index}"), recipe=self.recipe
            )
        with self.assertNumQueries(3):
            # target ref + COUNT + one page query (reviewer and target joined)
            response = self.client.get(
                f"/api/v1/recipes/{self.recipe.slug}/reviews/"
            )
        self.assertEqual(response.json()["count"], 4)
