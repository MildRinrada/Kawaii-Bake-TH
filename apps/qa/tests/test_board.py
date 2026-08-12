"""The board's decision numbers, filters and sorting."""

from __future__ import annotations

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.courses.tests.factories import create_published_course
from apps.qa.models import ThreadView
from apps.qa.tests.factories import create_answer, create_thread
from apps.recipes.tests.factories import create_published_recipe
from apps.users.tests.factories import create_user


class ThreadBoardTests(TestCase):
    """Counts are aggregated, sorts are stable, filters only narrow."""

    def setUp(self) -> None:
        """Two recipe threads and one course thread, with answers."""
        self.client = APIClient()
        self.asker = create_user(username="boardasker")
        self.helper = create_user(username="boardhelper")
        self.chef = create_user(username="boardchef")
        self.recipe = create_published_recipe(author=self.chef, slug="board-cake")
        self.course = create_published_course(instructor=self.chef, slug="board-course")

        self.answered = create_thread(author=self.asker, recipe=self.recipe)
        self.first = create_answer(thread=self.answered, author=self.helper)
        self.answered.accepted_answer = self.first
        self.answered.save(update_fields=["accepted_answer"])
        create_answer(thread=self.answered, author=self.chef)

        self.waiting = create_thread(author=self.asker, recipe=self.recipe)
        self.about_course = create_thread(author=self.asker, course=self.course)

    def _list(self, **params: str) -> list[dict]:
        """GET the board with query parameters."""
        response = self.client.get("/api/v1/qa/threads/", params)
        self.assertEqual(response.status_code, 200)
        return response.json()["results"]

    def test_counts_are_aggregated_not_stored(self) -> None:
        """Answers and readers are counted live, per thread."""
        rows = {row["id"]: row for row in self._list()}

        self.assertEqual(rows[self.answered.pk]["answer_count"], 2)
        self.assertEqual(rows[self.waiting.pk]["answer_count"], 0)
        self.assertIsNotNone(rows[self.answered.pk]["last_answer_at"])
        self.assertIsNone(rows[self.waiting.pk]["last_answer_at"])
        self.assertEqual(rows[self.answered.pk]["view_count"], 0)

    def test_opening_a_thread_counts_the_reader_once(self) -> None:
        """Refreshing does not inflate the number; anonymous is not counted."""
        self.client.get(f"/api/v1/qa/threads/{self.waiting.pk}/")
        self.assertEqual(ThreadView.objects.count(), 0)

        self.client.force_login(self.helper)
        self.client.get(f"/api/v1/qa/threads/{self.waiting.pk}/")
        self.client.get(f"/api/v1/qa/threads/{self.waiting.pk}/")
        self.assertEqual(
            ThreadView.objects.filter(thread=self.waiting).count(), 1
        )

        rows = {row["id"]: row for row in self._list()}
        self.assertEqual(rows[self.waiting.pk]["view_count"], 1)

    def test_resolved_filter_splits_the_board(self) -> None:
        """Waiting and answered are two disjoint, complete halves."""
        waiting = {row["id"] for row in self._list(resolved="false")}
        solved = {row["id"] for row in self._list(resolved="true")}

        self.assertEqual(solved, {self.answered.pk})
        self.assertEqual(waiting, {self.waiting.pk, self.about_course.pk})
        self.assertEqual(len(self._list()), 3)

    def test_target_filter_narrows_to_one_kind(self) -> None:
        """A course question is not a recipe question."""
        recipes = {row["id"] for row in self._list(target="recipe")}
        courses = {row["id"] for row in self._list(target="course")}

        self.assertEqual(recipes, {self.answered.pk, self.waiting.pk})
        self.assertEqual(courses, {self.about_course.pk})

    def test_ordering_by_activity_puts_unanswered_last(self) -> None:
        """A thread with no answers has no activity date to sort by."""
        rows = self._list(ordering="active")
        self.assertEqual(rows[0]["id"], self.answered.pk)
        self.assertIsNone(rows[-1]["last_answer_at"])

    def test_ordering_by_readers(self) -> None:
        """The most-read thread leads; ties fall back to newest."""
        ThreadView.objects.create(thread=self.waiting, user=self.helper)
        ThreadView.objects.create(thread=self.waiting, user=self.chef)

        rows = self._list(ordering="popular")
        self.assertEqual(rows[0]["id"], self.waiting.pk)
        self.assertEqual(rows[0]["view_count"], 2)

    def test_unknown_ordering_falls_back_to_newest(self) -> None:
        """A sort is a preference; junk must not 400 the board."""
        rows = self._list(ordering="banana")
        self.assertEqual([row["id"] for row in rows], [row["id"] for row in self._list()])

    def test_hidden_threads_stay_out_of_every_sort(self) -> None:
        """Sorting is not a way around visibility."""
        hidden = create_thread(author=self.asker, recipe=self.recipe)
        hidden.status = "hidden"
        hidden.save(update_fields=["status"])

        for ordering in ("latest", "active", "popular"):
            ids = {row["id"] for row in self._list(ordering=ordering)}
            self.assertNotIn(hidden.pk, ids, ordering)

    def test_needs_help_is_derivable_from_the_payload(self) -> None:
        """An old thread with no answers is visible as such to the client."""
        old = timezone.now() - timedelta(days=3)
        type(self.waiting).objects.filter(pk=self.waiting.pk).update(created_at=old)

        row = next(r for r in self._list() if r["id"] == self.waiting.pk)
        self.assertEqual(row["answer_count"], 0)
        self.assertIsNone(row["last_answer_at"])
        self.assertIsNone(row["accepted_answer"])
