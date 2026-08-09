"""API tests for the question bank surface."""

from __future__ import annotations

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.questions.constants import QuestionType
from apps.questions.services import question_service
from apps.questions.tests.factories import create_question
from apps.users.tests.factories import create_user


class QuestionApiTests(TestCase):
    """The bank is private, strict, and the one place correctness appears."""

    def setUp(self) -> None:
        self.client = APIClient()
        self.author = create_user(username="qauthor")
        self.other = create_user(username="qother")

    def test_anonymous_is_rejected_everywhere(self) -> None:
        question = create_question(author=self.author)
        for method, url in (
            ("get", reverse("questions:list")),
            ("post", reverse("questions:list")),
            ("get", reverse("questions:detail", args=[question.pk])),
            ("get", reverse("questions:tags")),
        ):
            with self.subTest(method=method, url=url):
                response = getattr(self.client, method)(url)
                self.assertEqual(response.status_code, 401)

    def test_listing_is_own_bank_only(self) -> None:
        create_question(author=self.author)
        create_question(author=self.other)

        self.client.force_login(self.author)
        response = self.client.get(reverse("questions:list"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 1)

    def test_owner_payload_carries_is_correct(self) -> None:
        question = create_question(author=self.author)
        self.client.force_login(self.author)

        response = self.client.get(reverse("questions:detail", args=[question.pk]))

        self.assertEqual(response.status_code, 200)
        flags = [c["is_correct"] for c in response.json()["choices"]]
        self.assertIn(True, flags)

    def test_someone_elses_question_is_404_not_403(self) -> None:
        question = create_question(author=self.author)
        self.client.force_login(self.other)

        response = self.client.get(reverse("questions:detail", args=[question.pk]))

        self.assertEqual(response.status_code, 404)

    def test_create_then_filter_by_type(self) -> None:
        self.client.force_login(self.author)
        response = self.client.post(
            reverse("questions:list"),
            {
                "question_type": QuestionType.TRUE_FALSE,
                "text": "Butter must be cold for laminating?",
                "choices": [
                    {"text": "True", "is_correct": True},
                    {"text": "False", "is_correct": False},
                ],
                "tags": ["croissant"],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        create_question(author=self.author)  # a single_choice one

        listed = self.client.get(
            reverse("questions:list"), {"type": QuestionType.TRUE_FALSE}
        )
        self.assertEqual(listed.json()["count"], 1)

    def test_invalid_choices_are_400_with_details(self) -> None:
        self.client.force_login(self.author)
        response = self.client.post(
            reverse("questions:list"),
            {
                "question_type": QuestionType.SINGLE_CHOICE,
                "text": "Which flour works?",
                "choices": [
                    {"text": "A", "is_correct": False},
                    {"text": "B", "is_correct": False},
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "invalid_choices")

    def test_frozen_patch_is_409_with_stable_code(self) -> None:
        question = create_question(author=self.author)
        question_service.freeze_questions(question_ids=[question.pk])
        self.client.force_login(self.author)

        response = self.client.patch(
            reverse("questions:detail", args=[question.pk]),
            {"text": "Rewritten history text"},
            format="json",
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "question_frozen")

    def test_unknown_query_parameter_is_400(self) -> None:
        self.client.force_login(self.author)
        response = self.client.get(reverse("questions:list"), {"tpe": "true_false"})
        self.assertEqual(response.status_code, 400)
