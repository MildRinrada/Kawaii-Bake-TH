"""Recommendation feeds: personalization, cold start, eligibility, privacy."""

from __future__ import annotations

from django.test import TestCase
from rest_framework.test import APIClient

from apps.courses.constants import CourseStatus, CourseVisibility, EnrollmentStatus
from apps.courses.tests.factories import (
    create_course,
    create_published_course,
    enroll_user,
)
from apps.favorites.tests.factories import create_favorite
from apps.recipes.constants import RecipeStatus, RecipeVisibility
from apps.recipes.tests.factories import create_category, create_published_recipe, create_recipe
from apps.recommendation.constants import REASON_ORDER
from apps.recommendation.services import recommendation_service
from apps.reviews.tests.factories import create_review
from apps.users.tests.factories import create_user

RECIPES_URL = "/api/v1/recommendations/recipes/"
COURSES_URL = "/api/v1/recommendations/courses/"


def recommended_ids(payload: dict, key: str) -> list[str]:
    return [item[key]["slug"] for item in payload["results"] if item[key]]


class RecipeRecommendationTests(TestCase):
    """The recipe feed ranks by real evidence and never leaks hidden content."""

    def setUp(self) -> None:
        self.client = APIClient()
        self.author = create_user(username="recauthor")
        self.other_author = create_user(username="recother")
        self.user = create_user(username="recviewer")
        self.bread = create_category(slug="bread")
        self.cake = create_category(slug="cake")

        self.bread_recipe = create_published_recipe(
            author=self.author, slug="rec-bread", categories=[self.bread]
        )
        self.cake_recipe = create_published_recipe(
            author=self.author, slug="rec-cake", categories=[self.cake]
        )

    def test_anonymous_cold_start_is_deterministic(self) -> None:
        first = self.client.get(RECIPES_URL)
        second = self.client.get(RECIPES_URL)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(
            recommended_ids(first.json(), "recipe"),
            recommended_ids(second.json(), "recipe"),
        )
        self.assertEqual(first.json()["count"], 2)

    def test_cold_start_prefers_popular_content(self) -> None:
        fans = [create_user() for _ in range(4)]
        for fan in fans:
            create_favorite(user=fan, recipe=self.cake_recipe)
            create_review(user=fan, recipe=self.cake_recipe, rating=5)

        ids = recommended_ids(self.client.get(RECIPES_URL).json(), "recipe")
        self.assertEqual(ids[0], self.cake_recipe.slug)

    def test_empty_history_matches_cold_start(self) -> None:
        newcomer = create_user(username="brandnew")
        anon = recommended_ids(self.client.get(RECIPES_URL).json(), "recipe")
        self.client.force_login(newcomer)
        logged_in = recommended_ids(self.client.get(RECIPES_URL).json(), "recipe")
        self.assertEqual(anon, logged_in)

    def test_favorite_signal_lifts_matching_category(self) -> None:
        seed = create_published_recipe(
            author=self.other_author, slug="seed-bread", categories=[self.bread]
        )
        create_favorite(user=self.user, recipe=seed)

        self.client.force_login(self.user)
        ids = recommended_ids(self.client.get(RECIPES_URL).json(), "recipe")
        self.assertEqual(ids[0], self.bread_recipe.slug)
        self.assertNotIn(seed.slug, ids)

    def test_positive_review_signal_lifts_matching_category(self) -> None:
        seed = create_published_recipe(
            author=self.other_author, slug="seed-cake", categories=[self.cake]
        )
        create_review(user=self.user, recipe=seed, rating=5)

        self.client.force_login(self.user)
        ids = recommended_ids(self.client.get(RECIPES_URL).json(), "recipe")
        self.assertEqual(ids[0], self.cake_recipe.slug)

    def test_profile_categories_alone_personalize(self) -> None:
        self.user.profile.favorite_categories.set([self.cake])

        self.client.force_login(self.user)
        payload = self.client.get(RECIPES_URL).json()
        ids = recommended_ids(payload, "recipe")
        self.assertEqual(ids[0], self.cake_recipe.slug)
        self.assertIn(
            "matches_your_favorite_categories", payload["results"][0]["reasons"]
        )

    def test_stacked_signals_outrank_single_signal(self) -> None:
        bread_seed = create_published_recipe(
            author=self.other_author, slug="stack-bread", categories=[self.bread]
        )
        cake_seed = create_published_recipe(
            author=self.other_author, slug="stack-cake", categories=[self.cake]
        )
        # Bread: favorite + positive review + profile. Cake: favorite only.
        create_favorite(user=self.user, recipe=bread_seed)
        create_review(user=self.user, recipe=bread_seed, rating=5)
        create_favorite(user=self.user, recipe=cake_seed)
        self.user.profile.favorite_categories.set([self.bread])

        self.client.force_login(self.user)
        ids = recommended_ids(self.client.get(RECIPES_URL).json(), "recipe")
        self.assertEqual(ids[0], self.bread_recipe.slug)

    def test_own_and_already_engaged_recipes_are_excluded(self) -> None:
        mine = create_published_recipe(author=self.user, slug="my-own")
        favorited = create_published_recipe(author=self.author, slug="already-fav")
        reviewed = create_published_recipe(author=self.author, slug="already-rev")
        create_favorite(user=self.user, recipe=favorited)
        create_review(user=self.user, recipe=reviewed, rating=2)

        self.client.force_login(self.user)
        ids = recommended_ids(self.client.get(RECIPES_URL).json(), "recipe")
        for excluded in (mine.slug, favorited.slug, reviewed.slug):
            self.assertNotIn(excluded, ids)

    def test_hidden_content_never_appears(self) -> None:
        create_recipe(
            author=self.author,
            slug="rec-private",
            status=RecipeStatus.PUBLISHED,
            visibility=RecipeVisibility.PRIVATE,
        )
        create_recipe(
            author=self.author,
            slug="rec-unlisted",
            status=RecipeStatus.PUBLISHED,
            visibility=RecipeVisibility.UNLISTED,
        )
        create_recipe(author=self.author, slug="rec-draft")

        staff = create_user(username="recstaff", is_staff=True)
        for viewer in (None, self.user, staff):
            if viewer is None:
                self.client.logout()
            else:
                self.client.force_login(viewer)
            ids = recommended_ids(self.client.get(RECIPES_URL).json(), "recipe")
            self.assertEqual(
                sorted(ids), sorted([self.bread_recipe.slug, self.cake_recipe.slug])
            )

    def test_no_duplicates_and_valid_reasons(self) -> None:
        self.client.force_login(self.user)
        payload = self.client.get(RECIPES_URL).json()
        ids = recommended_ids(payload, "recipe")
        self.assertEqual(len(ids), len(set(ids)))
        for item in payload["results"]:
            for reason in item["reasons"]:
                self.assertIn(reason, REASON_ORDER)

    def test_no_email_in_payload(self) -> None:
        create_favorite(user=self.user, recipe=self.bread_recipe)
        self.client.force_login(self.user)
        for url in (RECIPES_URL, COURSES_URL):
            self.assertNotIn("@example.com", self.client.get(url).content.decode())

    def test_pagination(self) -> None:
        response = self.client.get(RECIPES_URL, {"page_size": 1})
        payload = response.json()
        self.assertEqual(payload["count"], 2)
        self.assertEqual(len(payload["results"]), 1)
        self.assertIsNotNone(payload["next"])

    def test_unknown_query_param_rejected(self) -> None:
        response = self.client.get(RECIPES_URL, {"boost": "1"})
        self.assertEqual(response.status_code, 400)

    def test_service_query_count_anonymous(self) -> None:
        with self.assertNumQueries(4):
            recommendation_service.recommend_recipes(viewer_id=None)

    def test_service_query_count_with_full_history(self) -> None:
        seed = create_published_recipe(
            author=self.other_author, slug="count-seed", categories=[self.bread]
        )
        course = create_published_course(instructor=self.other_author)
        create_favorite(user=self.user, recipe=seed)
        create_review(user=self.user, recipe=self.cake_recipe, rating=5)
        enroll_user(user=self.user, course=course)

        # 12 since Phase 14: the personalization fact costs two queries
        # (profile+language join, then the favourite-category relation).
        with self.assertNumQueries(12):
            recommendation_service.recommend_recipes(viewer_id=self.user.id)

    def test_same_state_same_ordering(self) -> None:
        create_favorite(user=self.user, recipe=self.bread_recipe)
        first = recommendation_service.recommend_recipes(viewer_id=self.user.id)
        second = recommendation_service.recommend_recipes(viewer_id=self.user.id)
        self.assertEqual(first, second)


class CourseRecommendationTests(TestCase):
    """The course feed obeys enrollment policy and course visibility."""

    def setUp(self) -> None:
        self.client = APIClient()
        self.instructor = create_user(username="crecteacher")
        self.user = create_user(username="crecstudent")
        self.bread = create_category(slug="bread")
        self.cake = create_category(slug="cake")
        self.bread_course = create_published_course(
            instructor=self.instructor, slug="crec-bread", categories=[self.bread]
        )
        self.cake_course = create_published_course(
            instructor=self.instructor, slug="crec-cake", categories=[self.cake]
        )

    def test_anonymous_cold_start(self) -> None:
        payload = self.client.get(COURSES_URL).json()
        self.assertEqual(payload["count"], 2)
        self.assertEqual(
            recommended_ids(payload, "course"),
            recommended_ids(self.client.get(COURSES_URL).json(), "course"),
        )

    def test_enrolled_and_completed_courses_are_excluded(self) -> None:
        active = create_published_course(instructor=self.instructor, slug="crec-active")
        done = create_published_course(instructor=self.instructor, slug="crec-done")
        enroll_user(user=self.user, course=active)
        enroll_user(user=self.user, course=done, status=EnrollmentStatus.COMPLETED)

        self.client.force_login(self.user)
        ids = recommended_ids(self.client.get(COURSES_URL).json(), "course")
        self.assertNotIn(active.slug, ids)
        self.assertNotIn(done.slug, ids)

    def test_dropped_enrollment_returns_to_feed(self) -> None:
        dropped = create_published_course(instructor=self.instructor, slug="crec-drop")
        enroll_user(user=self.user, course=dropped, status=EnrollmentStatus.DROPPED)

        self.client.force_login(self.user)
        ids = recommended_ids(self.client.get(COURSES_URL).json(), "course")
        self.assertIn(dropped.slug, ids)

    def test_enrollment_categories_personalize(self) -> None:
        seed = create_published_course(
            instructor=create_user(username="crecother"),
            slug="crec-seed",
            categories=[self.cake],
        )
        enroll_user(user=self.user, course=seed)

        self.client.force_login(self.user)
        payload = self.client.get(COURSES_URL).json()
        ids = recommended_ids(payload, "course")
        self.assertEqual(ids[0], self.cake_course.slug)
        self.assertIn("based_on_your_courses", payload["results"][0]["reasons"])

    def test_hidden_courses_never_appear(self) -> None:
        create_course(instructor=self.instructor, slug="crec-draft")
        create_course(
            instructor=self.instructor,
            slug="crec-priv",
            status=CourseStatus.PUBLISHED,
            visibility=CourseVisibility.PRIVATE,
        )
        create_course(
            instructor=self.instructor,
            slug="crec-arch",
            status=CourseStatus.ARCHIVED,
            visibility=CourseVisibility.PUBLIC,
        )

        ids = recommended_ids(self.client.get(COURSES_URL).json(), "course")
        self.assertEqual(
            sorted(ids), sorted([self.bread_course.slug, self.cake_course.slug])
        )

    def test_archived_stays_out_even_for_enrolled_student(self) -> None:
        archived = create_course(
            instructor=self.instructor,
            slug="crec-arch2",
            status=CourseStatus.ARCHIVED,
            visibility=CourseVisibility.PUBLIC,
        )
        enroll_user(user=self.user, course=archived)

        self.client.force_login(self.user)
        ids = recommended_ids(self.client.get(COURSES_URL).json(), "course")
        self.assertNotIn(archived.slug, ids)

    def test_service_query_count_anonymous(self) -> None:
        with self.assertNumQueries(4):
            recommendation_service.recommend_courses(viewer_id=None)
