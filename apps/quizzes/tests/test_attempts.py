"""Attempt lifecycle tests: start (freeze + snapshot), submit, abandon.

The two regression tests this file exists for:

* ``test_start_freezes_questions_in_the_same_transaction`` — the W2 fix
  (freeze at start, not submit).
* ``test_submit_grades_against_the_snapshot_not_the_live_composition`` — the
  W1 fix (``points_possible`` snapshotted, so mid-attempt recomposition
  cannot corrupt grading).
"""

from __future__ import annotations

import json

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.questions.constants import QuestionType
from apps.questions.models import Question
from apps.questions.tests.factories import (
    correct_choice_ids,
    create_question,
    wrong_choice_id,
)
from apps.quizzes.constants import AttemptStatus, QuizStatus
from apps.quizzes.exceptions import (
    AttemptAlreadySubmittedError,
    InvalidSubmissionError,
    NoOpenAttemptError,
    QuizNotAvailableError,
    QuizNotVisibleError,
)
from apps.quizzes.models import QuizAttempt
from apps.quizzes.services import attempt_service, quiz_service
from apps.quizzes.tests.factories import compose, create_published_quiz
from apps.users.tests.factories import create_user


def _answer(question: Question, choice_ids: list[int]) -> dict[str, object]:
    return {"question_id": question.pk, "choice_ids": choice_ids}


class StartAttemptTests(TestCase):
    """Start = freeze + snapshot, atomically and idempotently."""

    def setUp(self) -> None:
        self.owner = create_user(username="atowner")
        self.student = create_user(username="atstudent")
        self.q1 = create_question(author=self.owner)
        self.q2 = create_question(
            author=self.owner, question_type=QuestionType.TRUE_FALSE
        )
        self.quiz = create_published_quiz(owner=self.owner)
        compose(self.quiz, [self.q1, self.q2], points=2)

    def test_start_creates_snapshot_rows_with_points_and_max_score(self) -> None:
        attempt, created = attempt_service.start_attempt(
            user_id=self.student.id, slug=self.quiz.slug
        )

        self.assertTrue(created)
        self.assertEqual(attempt.max_score, 4)
        rows = list(attempt.answers.order_by("position"))
        self.assertEqual([r.question_id for r in rows], [self.q1.pk, self.q2.pk])
        self.assertEqual([r.points_possible for r in rows], [2, 2])
        self.assertTrue(all(r.was_correct is None for r in rows))

    def test_start_freezes_questions_in_the_same_transaction(self) -> None:
        attempt_service.start_attempt(user_id=self.student.id, slug=self.quiz.slug)

        for question in (self.q1, self.q2):
            with self.subTest(question=question.pk):
                self.assertIsNotNone(
                    Question.objects.get(pk=question.pk).frozen_at
                )

    def test_second_student_starts_despite_frozen_questions(self) -> None:
        attempt_service.start_attempt(user_id=self.student.id, slug=self.quiz.slug)
        second = create_user(username="atsecond")

        _, created = attempt_service.start_attempt(
            user_id=second.id, slug=self.quiz.slug
        )

        self.assertTrue(created)

    def test_start_is_idempotent_per_user(self) -> None:
        first, _ = attempt_service.start_attempt(
            user_id=self.student.id, slug=self.quiz.slug
        )
        second, created = attempt_service.start_attempt(
            user_id=self.student.id, slug=self.quiz.slug
        )
        self.assertFalse(created)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(QuizAttempt.objects.count(), 1)

    def test_start_requires_published(self) -> None:
        # A stranger sees a drafted quiz as 404 — the visibility layer.
        self.quiz.status = QuizStatus.DRAFT
        self.quiz.save(update_fields=["status"])
        with self.assertRaises(QuizNotVisibleError):
            attempt_service.start_attempt(
                user_id=self.student.id, slug=self.quiz.slug
            )

        # The owner sees it, but starting is still blocked — the status layer.
        with self.assertRaises(QuizNotAvailableError):
            attempt_service.start_attempt(
                user_id=self.owner.id, slug=self.quiz.slug
            )

    def test_archived_quiz_is_readable_but_not_startable_after_attempting(self) -> None:
        attempt_service.start_attempt(user_id=self.student.id, slug=self.quiz.slug)
        attempt_service.submit_attempt(
            user_id=self.student.id, slug=self.quiz.slug, answers=[]
        )
        self.quiz.status = QuizStatus.ARCHIVED
        self.quiz.save(update_fields=["status"])

        # History remains reachable through the archived-but-attempted branch…
        quiz = attempt_service.require_visible_quiz(
            user_id=self.student.id, slug=self.quiz.slug
        )
        self.assertEqual(quiz.status, QuizStatus.ARCHIVED)

        # …but no new attempt may start.
        with self.assertRaises(QuizNotAvailableError):
            attempt_service.start_attempt(
                user_id=self.student.id, slug=self.quiz.slug
            )


class SubmitAttemptTests(TestCase):
    """Grading reads only the snapshot and the frozen bank."""

    def setUp(self) -> None:
        self.owner = create_user(username="subowner")
        self.student = create_user(username="substudent")
        self.q1 = create_question(author=self.owner)  # single, 1 correct
        self.q2 = create_question(
            author=self.owner,
            question_type=QuestionType.MULTIPLE_CHOICE,
            choices=[("A", True), ("B", True), ("C", False)],
        )
        self.quiz = create_published_quiz(owner=self.owner, pass_percent=50)
        compose(self.quiz, [self.q1, self.q2])

    def _start(self) -> QuizAttempt:
        attempt, _ = attempt_service.start_attempt(
            user_id=self.student.id, slug=self.quiz.slug
        )
        return attempt

    def test_submit_scores_and_denormalizes(self) -> None:
        self._start()
        attempt, results = attempt_service.submit_attempt(
            user_id=self.student.id,
            slug=self.quiz.slug,
            answers=[
                _answer(self.q1, correct_choice_ids(self.q1)),
                _answer(self.q2, [wrong_choice_id(self.q2)]),
            ],
        )

        self.assertEqual(attempt.status, AttemptStatus.SUBMITTED)
        self.assertIsNotNone(attempt.submitted_at)
        self.assertEqual(attempt.score, 1)
        self.assertEqual(attempt.max_score, 2)
        self.assertEqual(attempt.correct_count, 1)
        self.assertEqual(attempt.incorrect_count, 1)
        self.assertTrue(attempt.passed)  # 50.00 >= 50
        rows = {r.question_id: r for r in attempt.answers.all()}
        self.assertTrue(rows[self.q1.pk].was_correct)
        self.assertFalse(rows[self.q2.pk].was_correct)
        self.assertEqual(
            sorted(c.pk for c in rows[self.q1.pk].selected_choices.all()),
            sorted(correct_choice_ids(self.q1)),
        )

    def test_omitted_question_is_graded_as_skipped(self) -> None:
        self._start()
        attempt, _ = attempt_service.submit_attempt(
            user_id=self.student.id,
            slug=self.quiz.slug,
            answers=[_answer(self.q1, correct_choice_ids(self.q1))],
        )
        self.assertEqual(attempt.incorrect_count, 1)

    def test_submit_grades_against_the_snapshot_not_the_live_composition(self) -> None:
        self._start()
        # Instructor recomposes mid-attempt: q2 out, a new question in.
        q3 = create_question(author=self.owner)
        quiz_service.update_quiz(
            slug=self.quiz.slug,
            viewer_id=self.owner.id,
            data={"question_ids": [self.q1.pk, q3.pk]},
        )

        attempt, _ = attempt_service.submit_attempt(
            user_id=self.student.id,
            slug=self.quiz.slug,
            answers=[
                _answer(self.q1, correct_choice_ids(self.q1)),
                _answer(self.q2, correct_choice_ids(self.q2)),  # still the snapshot's
            ],
        )

        self.assertEqual(attempt.score, 2)
        self.assertEqual(attempt.max_score, 2)
        self.assertEqual(
            {r.question_id for r in attempt.answers.all()},
            {self.q1.pk, self.q2.pk},
        )

    def test_double_submit_is_409(self) -> None:
        self._start()
        attempt_service.submit_attempt(
            user_id=self.student.id, slug=self.quiz.slug, answers=[]
        )
        with self.assertRaises(NoOpenAttemptError):
            attempt_service.submit_attempt(
                user_id=self.student.id, slug=self.quiz.slug, answers=[]
            )

    def test_submission_diff_is_reported(self) -> None:
        self._start()
        outsider_question = create_question(author=self.owner)
        with self.assertRaises(InvalidSubmissionError) as caught:
            attempt_service.submit_attempt(
                user_id=self.student.id,
                slug=self.quiz.slug,
                answers=[
                    _answer(outsider_question, []),
                    _answer(self.q1, []),
                    _answer(self.q1, []),
                ],
            )
        details = caught.exception.details
        self.assertEqual(details["unknown_question_ids"], [outsider_question.pk])
        self.assertEqual(details["duplicate_question_ids"], [self.q1.pk])

    def test_choice_from_another_question_is_rejected(self) -> None:
        self._start()
        with self.assertRaises(InvalidSubmissionError) as caught:
            attempt_service.submit_attempt(
                user_id=self.student.id,
                slug=self.quiz.slug,
                answers=[_answer(self.q1, [wrong_choice_id(self.q2)])],
            )
        self.assertIn("unknown_choice_ids", caught.exception.details)

    def test_abandon_deletes_open_attempt_but_never_submitted(self) -> None:
        attempt = self._start()
        attempt_service.abandon_attempt(
            user_id=self.student.id, slug=self.quiz.slug, attempt_id=attempt.pk
        )
        self.assertFalse(QuizAttempt.objects.filter(pk=attempt.pk).exists())

        attempt = self._start()
        attempt_service.submit_attempt(
            user_id=self.student.id, slug=self.quiz.slug, answers=[]
        )
        with self.assertRaises(AttemptAlreadySubmittedError):
            attempt_service.abandon_attempt(
                user_id=self.student.id, slug=self.quiz.slug, attempt_id=attempt.pk
            )


class RefreezeCommandTests(TestCase):
    """The rebuild command restores missing freezes and never unfreezes."""

    def test_refreeze_restores_missing_state(self) -> None:
        owner = create_user(username="rfowner")
        student = create_user(username="rfstudent")
        question = create_question(author=owner)
        quiz = create_published_quiz(owner=owner)
        compose(quiz, [question])
        attempt_service.start_attempt(user_id=student.id, slug=quiz.slug)

        # Simulate drift: an admin cleared the stamp.
        Question.objects.filter(pk=question.pk).update(frozen_at=None)

        call_command("refreeze_questions")

        self.assertIsNotNone(Question.objects.get(pk=question.pk).frozen_at)


class AnswerKeyLeakSweepTests(TestCase):
    """No taker-facing payload may ever contain ``is_correct``."""

    def setUp(self) -> None:
        self.client = APIClient()
        self.owner = create_user(username="lkowner")
        self.student = create_user(username="lkstudent")
        question = create_question(author=self.owner)
        self.quiz = create_published_quiz(owner=self.owner)
        compose(self.quiz, [question])

    def _assert_clean(self, payload: object) -> None:
        self.assertNotIn("is_correct", json.dumps(payload))

    def test_quiz_detail_start_submit_and_review_are_clean(self) -> None:
        detail = self.client.get(reverse("quizzes:detail", args=[self.quiz.slug]))
        self.assertEqual(detail.status_code, 200)
        self._assert_clean(detail.json())
        # Choices arrive in position order, never correct-first.
        choices = detail.json()["questions"][0]["choices"]
        self.assertEqual([c["position"] for c in choices], sorted(c["position"] for c in choices))

        self.client.force_login(self.student)
        start = self.client.post(reverse("quizzes:start", args=[self.quiz.slug]))
        self.assertEqual(start.status_code, 201)
        self._assert_clean(start.json())

        submit = self.client.post(
            reverse("quizzes:submit", args=[self.quiz.slug]),
            {"answers": []},
            format="json",
        )
        self.assertEqual(submit.status_code, 200)
        self._assert_clean(submit.json())

        attempt_id = submit.json()["id"]
        review = self.client.get(
            reverse("quizzes:attempt-detail", args=[self.quiz.slug, attempt_id])
        )
        self.assertEqual(review.status_code, 200)
        self._assert_clean(review.json())

        history = self.client.get(reverse("quizzes:attempts", args=[self.quiz.slug]))
        self.assertEqual(history.status_code, 200)
        self._assert_clean(history.json())
