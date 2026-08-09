"""Service-level tests: composition, publish gate, delete rules."""

from __future__ import annotations

from django.test import TestCase

from apps.questions.exceptions import QuestionInUseError
from apps.questions.services import question_service
from apps.questions.tests.factories import create_question
from apps.quizzes.constants import QuizStatus
from apps.quizzes.exceptions import (
    InvalidQuizQuestionError,
    QuizNotPublishableError,
    QuizNotVisibleError,
    QuizSlugImmutableError,
)
from apps.quizzes.models import QuizQuestion
from apps.quizzes.services import publish_service, quiz_service
from apps.quizzes.tests.factories import THAI_QUIZ_TITLE, compose, create_quiz
from apps.users.tests.factories import create_user


class QuizCompositionTests(TestCase):
    """A quiz references the bank; the bank rules the references."""

    def setUp(self) -> None:
        self.owner = create_user(username="qsowner")
        self.other = create_user(username="qsother")

    def test_create_with_thai_title_composes_in_order(self) -> None:
        q1 = create_question(author=self.owner)
        q2 = create_question(author=self.owner)

        quiz = quiz_service.create_quiz(
            owner_id=self.owner.id,
            data={
                "title": THAI_QUIZ_TITLE,
                "question_ids": [q2.pk, q1.pk],
            },
        )

        self.assertEqual(quiz.status, QuizStatus.DRAFT)
        self.assertNotEqual(quiz.slug, "")
        self.assertEqual(
            list(
                QuizQuestion.objects.filter(quiz=quiz)
                .order_by("position")
                .values_list("question_id", flat=True)
            ),
            [q2.pk, q1.pk],
        )

    def test_foreign_and_unknown_questions_are_the_same_rejection(self) -> None:
        someone_elses = create_question(author=self.other)
        with self.assertRaises(InvalidQuizQuestionError) as caught:
            quiz_service.create_quiz(
                owner_id=self.owner.id,
                data={"title": "My quiz", "question_ids": [someone_elses.pk, 999999]},
            )
        self.assertEqual(
            caught.exception.details["unknown_ids"], [someone_elses.pk, 999999]
        )

    def test_duplicate_question_ids_are_rejected_with_diff(self) -> None:
        question = create_question(author=self.owner)
        with self.assertRaises(InvalidQuizQuestionError) as caught:
            quiz_service.create_quiz(
                owner_id=self.owner.id,
                data={"title": "My quiz", "question_ids": [question.pk, question.pk]},
            )
        self.assertEqual(caught.exception.details["duplicate_ids"], [question.pk])

    def test_replace_composition_is_reordering(self) -> None:
        q1 = create_question(author=self.owner)
        q2 = create_question(author=self.owner)
        quiz = create_quiz(owner=self.owner)
        compose(quiz, [q1, q2])

        quiz_service.update_quiz(
            slug=quiz.slug,
            viewer_id=self.owner.id,
            data={"question_ids": [q2.pk, q1.pk]},
        )

        self.assertEqual(
            list(
                QuizQuestion.objects.filter(quiz=quiz)
                .order_by("position")
                .values_list("question_id", flat=True)
            ),
            [q2.pk, q1.pk],
        )

    def test_published_quiz_cannot_be_emptied(self) -> None:
        question = create_question(author=self.owner)
        quiz = create_quiz(owner=self.owner, status=QuizStatus.PUBLISHED)
        compose(quiz, [question])

        with self.assertRaises(InvalidQuizQuestionError):
            quiz_service.update_quiz(
                slug=quiz.slug, viewer_id=self.owner.id, data={"question_ids": []}
            )

    def test_deleting_a_question_used_by_a_quiz_is_409(self) -> None:
        question = create_question(author=self.owner)
        quiz = create_quiz(owner=self.owner)
        compose(quiz, [question])

        with self.assertRaises(QuestionInUseError):
            question_service.delete_question(
                question_id=question.pk, viewer_id=self.owner.id
            )


class PublishGateTests(TestCase):
    """Publish collects every failure, including the bank's verdict."""

    def setUp(self) -> None:
        self.owner = create_user(username="qpowner")

    def test_gate_collects_all_problems(self) -> None:
        quiz = create_quiz(owner=self.owner, title="Hi", description="short")

        with self.assertRaises(QuizNotPublishableError) as caught:
            publish_service.publish(slug=quiz.slug, viewer_id=self.owner.id)

        details = caught.exception.details
        self.assertIn("title", details)
        self.assertIn("description", details)
        self.assertIn("questions", details)

    def test_gate_reports_invalid_answers_per_question(self) -> None:
        # Build a stored-invalid question: bypass the service on purpose.
        question = create_question(
            author=self.owner, choices=[("Only choice", True)]
        )
        quiz = create_quiz(owner=self.owner)
        compose(quiz, [question])

        with self.assertRaises(QuizNotPublishableError) as caught:
            publish_service.publish(slug=quiz.slug, viewer_id=self.owner.id)

        self.assertIn(str(question.pk), caught.exception.details["questions"])

    def test_publish_stamps_once_and_freezes_slug(self) -> None:
        question = create_question(author=self.owner)
        quiz = create_quiz(owner=self.owner)
        compose(quiz, [question])

        published = publish_service.publish(slug=quiz.slug, viewer_id=self.owner.id)
        first_stamp = published.published_at
        self.assertIsNotNone(first_stamp)

        publish_service.unpublish(slug=quiz.slug, viewer_id=self.owner.id)
        republished = publish_service.publish(slug=quiz.slug, viewer_id=self.owner.id)
        self.assertEqual(republished.published_at, first_stamp)

        with self.assertRaises(QuizSlugImmutableError):
            quiz_service.update_quiz(
                slug=quiz.slug, viewer_id=self.owner.id, data={"slug": "new-slug"}
            )

    def test_stranger_cannot_transition_and_gets_404(self) -> None:
        stranger = create_user(username="qpstranger")
        question = create_question(author=self.owner)
        quiz = create_quiz(owner=self.owner)
        compose(quiz, [question])

        with self.assertRaises(QuizNotVisibleError):
            publish_service.publish(slug=quiz.slug, viewer_id=stranger.id)
