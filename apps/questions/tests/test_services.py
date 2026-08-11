"""Service-level tests: choice rules, the frozen gate, and freeze semantics."""

from __future__ import annotations

from django.test import TestCase

from apps.questions.constants import QuestionType
from apps.questions.exceptions import (
    InvalidQuestionChoicesError,
    QuestionFrozenError,
    QuestionNotFoundError,
)
from apps.questions.models import Question
from apps.questions.repositories import question_repository
from apps.questions.services import question_service
from apps.questions.tests.factories import THAI_QUESTION_TEXT, create_question
from apps.questions.validators.question_validator import choice_problems
from apps.users.tests.factories import create_user


class ChoiceValidationTests(TestCase):
    """The per-type answer rules, checked as a matrix."""

    def _problems(self, question_type: str, choices: list[tuple[str, bool]]) -> list[str]:
        return choice_problems(
            question_type=question_type,
            choices=[{"text": t, "is_correct": c} for t, c in choices],
        )

    def test_valid_shapes_have_no_problems(self) -> None:
        cases = {
            QuestionType.SINGLE_CHOICE: [("A", True), ("B", False)],
            QuestionType.MULTIPLE_CHOICE: [("A", True), ("B", True), ("C", False)],
            QuestionType.TRUE_FALSE: [("True", True), ("False", False)],
        }
        for question_type, choices in cases.items():
            with self.subTest(question_type=question_type):
                self.assertEqual(self._problems(question_type, choices), [])

    def test_invalid_shapes_are_rejected(self) -> None:
        cases = [
            (QuestionType.SINGLE_CHOICE, [("A", True)]),  # too few
            (QuestionType.SINGLE_CHOICE, [("A", True), ("B", True)]),  # 2 correct
            (QuestionType.SINGLE_CHOICE, [("A", False), ("B", False)]),  # none correct
            (QuestionType.SINGLE_CHOICE, [("A", True), ("a", False)]),  # duplicate text
            (QuestionType.SINGLE_CHOICE, [("A", True), ("  ", False)]),  # blank
            (QuestionType.MULTIPLE_CHOICE, [("A", False), ("B", False)]),  # none correct
            (QuestionType.TRUE_FALSE, [("T", True), ("F", False), ("N", False)]),  # arity
        ]
        for question_type, choices in cases:
            with self.subTest(question_type=question_type, choices=choices):
                self.assertTrue(self._problems(question_type, choices))

    def test_create_collects_every_problem(self) -> None:
        author = create_user(username="author1")
        with self.assertRaises(InvalidQuestionChoicesError) as caught:
            question_service.create_question(
                author_id=author.id,
                data={
                    "question_type": QuestionType.SINGLE_CHOICE,
                    "text": "Which flour?",
                    "choices": [
                        {"text": "Bread flour", "is_correct": True},
                        {"text": "bread flour", "is_correct": True},
                    ],
                },
            )
        problems = caught.exception.details["choices"]
        self.assertEqual(len(problems), 2)  # duplicate + two-correct


class QuestionCrudTests(TestCase):
    """Create, update and delete against the ownership and frozen rules."""

    def setUp(self) -> None:
        self.author = create_user(username="author2")
        self.other = create_user(username="other2")

    def test_create_persists_thai_text_choices_and_tags(self) -> None:
        question = question_service.create_question(
            author_id=self.author.id,
            data={
                "question_type": QuestionType.SINGLE_CHOICE,
                "text": THAI_QUESTION_TEXT,
                "explanation": "แป้งขนมปังมีโปรตีนสูง",
                "choices": [
                    {"text": "แป้งขนมปัง", "is_correct": True},
                    {"text": "แป้งเค้ก", "is_correct": False},
                ],
                "tags": ["ครัวซอง", "แป้ง"],
            },
        )
        self.assertEqual(question.text, THAI_QUESTION_TEXT)
        self.assertEqual(question.choices.count(), 2)
        self.assertEqual(question.tags.count(), 2)
        self.assertEqual(
            list(question.choices.values_list("position", flat=True)), [0, 1]
        )

    def test_tags_are_case_insensitively_shared(self) -> None:
        first = create_question(author=self.author)
        question_service.update_question(
            question_id=first.pk, viewer_id=self.author.id, data={"tags": ["Bread"]}
        )
        second = create_question(author=self.author)
        question_service.update_question(
            question_id=second.pk, viewer_id=self.author.id, data={"tags": ["bread"]}
        )
        self.assertEqual(
            first.tags.first().pk, second.tags.first().pk
        )

    def test_someone_elses_question_is_the_same_404(self) -> None:
        question = create_question(author=self.author)
        with self.assertRaises(QuestionNotFoundError):
            question_service.get_question(
                question_id=question.pk, viewer_id=self.other.id
            )
        with self.assertRaises(QuestionNotFoundError):
            question_service.update_question(
                question_id=question.pk, viewer_id=self.other.id, data={"text": "x" * 10}
            )

    def test_type_change_requires_choices(self) -> None:
        question = create_question(author=self.author)
        with self.assertRaises(InvalidQuestionChoicesError):
            question_service.update_question(
                question_id=question.pk,
                viewer_id=self.author.id,
                data={"question_type": QuestionType.TRUE_FALSE},
            )

    def test_replace_choices_renumbers_densely(self) -> None:
        question = create_question(author=self.author)
        updated = question_service.update_question(
            question_id=question.pk,
            viewer_id=self.author.id,
            data={
                "choices": [
                    {"text": "X", "is_correct": False},
                    {"text": "Y", "is_correct": True},
                    {"text": "Z", "is_correct": False},
                ]
            },
        )
        self.assertEqual(
            list(updated.choices.values_list("text", "position")),
            [("X", 0), ("Y", 1), ("Z", 2)],
        )


class FreezeTests(TestCase):
    """freeze_questions is idempotent; the gate blocks content, not metadata."""

    def setUp(self) -> None:
        self.author = create_user(username="author3")
        self.question = create_question(author=self.author)

    def test_freeze_stamps_once_and_is_idempotent(self) -> None:
        question_service.freeze_questions(question_ids=[self.question.pk])
        first_stamp = Question.objects.get(pk=self.question.pk).frozen_at
        self.assertIsNotNone(first_stamp)

        # Second freeze  the second student starting the same quiz.
        question_service.freeze_questions(question_ids=[self.question.pk])
        self.assertEqual(
            Question.objects.get(pk=self.question.pk).frozen_at, first_stamp
        )

    def test_freeze_of_unknown_id_raises(self) -> None:
        with self.assertRaises(QuestionNotFoundError):
            question_service.freeze_questions(question_ids=[self.question.pk, 999999])

    def test_frozen_content_cannot_change(self) -> None:
        question_service.freeze_questions(question_ids=[self.question.pk])
        for payload in (
            {"text": "New text for the question"},
            {"choices": [{"text": "A", "is_correct": True}, {"text": "B", "is_correct": False}]},
        ):
            with self.subTest(payload=list(payload)):
                with self.assertRaises(QuestionFrozenError):
                    question_service.update_question(
                        question_id=self.question.pk,
                        viewer_id=self.author.id,
                        data=payload,
                    )

    def test_frozen_metadata_stays_editable(self) -> None:
        question_service.freeze_questions(question_ids=[self.question.pk])
        updated = question_service.update_question(
            question_id=self.question.pk,
            viewer_id=self.author.id,
            data={"explanation": "Because gluten.", "difficulty": "hard", "tags": ["bread"]},
        )
        self.assertEqual(updated.explanation, "Because gluten.")
        self.assertEqual(updated.difficulty, "hard")
        self.assertEqual(updated.tags.count(), 1)

    def test_frozen_question_cannot_be_deleted(self) -> None:
        question_service.freeze_questions(question_ids=[self.question.pk])
        with self.assertRaises(QuestionFrozenError):
            question_service.delete_question(
                question_id=self.question.pk, viewer_id=self.author.id
            )
        self.assertTrue(Question.objects.filter(pk=self.question.pk).exists())

    def test_unfrozen_question_deletes_cleanly(self) -> None:
        question_service.delete_question(
            question_id=self.question.pk, viewer_id=self.author.id
        )
        self.assertFalse(Question.objects.filter(pk=self.question.pk).exists())

    def test_gate_write_reports_conflict_via_rowcount(self) -> None:
        # The repository primitive itself: 1 row before freeze, 0 after 
        # the "affected rows != expected" conflict signal from the design.
        self.assertTrue(
            question_repository.acquire_edit_gate(question_id=self.question.pk)
        )
        question_repository.freeze(question_ids=[self.question.pk])
        self.assertFalse(
            question_repository.acquire_edit_gate(question_id=self.question.pk)
        )
