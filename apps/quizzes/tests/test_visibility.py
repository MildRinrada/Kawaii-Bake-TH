"""The quiz visibility matrix, enforced as a parametrised sweep."""

from __future__ import annotations

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.quizzes.constants import QuizStatus, QuizVisibility
from apps.quizzes.models import QuizAttempt
from apps.quizzes.tests.factories import create_quiz
from apps.users.tests.factories import create_user


class QuizVisibilityMatrixTests(TestCase):
    """3 statuses × 3 visibilities × viewer classes × list/detail."""

    @classmethod
    def setUpTestData(cls) -> None:
        cls.owner = create_user(username="qvowner")
        cls.stranger = create_user(username="qvstranger")
        cls.staff = create_user(username="qvstaff", is_staff=True)

    def _make(self, status: str, visibility: str) -> object:
        return create_quiz(
            owner=self.owner,
            status=status,
            visibility=visibility,
            published_at=timezone.now() if status != QuizStatus.DRAFT else None,
        )

    def test_matrix(self) -> None:
        expectations = {
            # (status, visibility): (anon_list, anon_detail, stranger_detail)
            (QuizStatus.PUBLISHED, QuizVisibility.PUBLIC): (True, 200, 200),
            (QuizStatus.PUBLISHED, QuizVisibility.UNLISTED): (False, 200, 200),
            (QuizStatus.PUBLISHED, QuizVisibility.PRIVATE): (False, 404, 404),
            (QuizStatus.DRAFT, QuizVisibility.PUBLIC): (False, 404, 404),
            (QuizStatus.DRAFT, QuizVisibility.UNLISTED): (False, 404, 404),
            (QuizStatus.DRAFT, QuizVisibility.PRIVATE): (False, 404, 404),
            (QuizStatus.ARCHIVED, QuizVisibility.PUBLIC): (False, 404, 404),
            (QuizStatus.ARCHIVED, QuizVisibility.UNLISTED): (False, 404, 404),
            (QuizStatus.ARCHIVED, QuizVisibility.PRIVATE): (False, 404, 404),
        }
        anon = APIClient()
        stranger_client = APIClient()
        stranger_client.force_login(self.stranger)
        owner_client = APIClient()
        owner_client.force_login(self.owner)
        staff_client = APIClient()
        staff_client.force_login(self.staff)

        for (status, visibility), (listed, anon_detail, stranger_detail) in expectations.items():
            quiz = self._make(status, visibility)
            url = reverse("quizzes:detail", args=[quiz.slug])
            with self.subTest(status=status, visibility=visibility):
                anon_list = anon.get(reverse("quizzes:list")).json()
                slugs = [row["slug"] for row in anon_list["results"]]
                self.assertEqual(quiz.slug in slugs, listed)

                self.assertEqual(anon.get(url).status_code, anon_detail)
                self.assertEqual(
                    stranger_client.get(url).status_code, stranger_detail
                )
                # Owner and staff always see their material.
                self.assertEqual(owner_client.get(url).status_code, 200)
                self.assertEqual(staff_client.get(url).status_code, 200)

    def test_archived_quiz_stays_readable_to_someone_who_attempted_it(self) -> None:
        quiz = self._make(QuizStatus.ARCHIVED, QuizVisibility.PUBLIC)
        QuizAttempt.objects.create(
            user=self.stranger,
            quiz=quiz,
            status="submitted",
            started_at=timezone.now(),
            submitted_at=timezone.now(),
        )
        client = APIClient()
        client.force_login(self.stranger)

        response = client.get(reverse("quizzes:detail", args=[quiz.slug]))

        self.assertEqual(response.status_code, 200)

    def test_scope_mine_requires_login_and_pins_to_owner(self) -> None:
        self._make(QuizStatus.DRAFT, QuizVisibility.PRIVATE)
        anon = APIClient()
        self.assertEqual(
            anon.get(reverse("quizzes:list"), {"scope": "mine"}).status_code, 401
        )

        owner_client = APIClient()
        owner_client.force_login(self.owner)
        response = owner_client.get(reverse("quizzes:list"), {"scope": "mine"})
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(response.json()["count"], 1)

        stranger_client = APIClient()
        stranger_client.force_login(self.stranger)
        self.assertEqual(
            stranger_client.get(reverse("quizzes:list"), {"scope": "mine"}).json()["count"],
            0,
        )

    def test_scope_all_narrows_silently_for_non_staff(self) -> None:
        self._make(QuizStatus.DRAFT, QuizVisibility.PRIVATE)
        client = APIClient()
        client.force_login(self.stranger)

        response = client.get(reverse("quizzes:list"), {"scope": "all"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 0)
