"""API tests for Q&A: endpoints, visibility, privacy, no N+1."""

from __future__ import annotations

from unittest import mock

from django.test import TestCase
from rest_framework.test import APIClient

from apps.notifications.models import Notification
from apps.qa.constants import ThreadStatus
from apps.qa.tests.factories import create_answer, create_thread
from apps.recipes.tests.factories import create_published_recipe
from apps.users.tests.factories import create_user


class ThreadApiTests(TestCase):
    """The thread surface."""

    def setUp(self) -> None:
        self.client = APIClient()
        self.asker = create_user(username="qapiasker")
        self.helper = create_user(username="qapihelper")
        self.chef = create_user(username="qapichef")
        self.recipe = create_published_recipe(author=self.chef, slug="qapi-cake")

    def test_anonymous_reads_but_cannot_write(self) -> None:
        thread = create_thread(author=self.asker, recipe=self.recipe)

        self.assertEqual(self.client.get("/api/v1/qa/threads/").status_code, 200)
        self.assertEqual(
            self.client.get(f"/api/v1/qa/threads/{thread.pk}/").status_code, 200
        )
        created = self.client.post("/api/v1/qa/threads/", {})
        self.assertEqual(created.status_code, 401)

    def test_create_thread_roundtrip(self) -> None:
        self.client.force_login(self.asker)
        response = self.client.post(
            "/api/v1/qa/threads/",
            {
                "target_type": "recipe",
                "target_slug": self.recipe.slug,
                "title": "แป้งเหนียวเกินไปทำไงดี?",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body["author_handle"], "qapiasker")
        self.assertEqual(body["recipe"]["slug"], "qapi-cake")
        self.assertIsNone(body["accepted_answer"])

    def test_answer_accept_flow_over_http(self) -> None:
        thread = create_thread(author=self.asker, recipe=self.recipe)

        self.client.force_login(self.helper)
        answered = self.client.post(
            f"/api/v1/qa/threads/{thread.pk}/answers/",
            {"body": "นวดน้อยลงหน่อยค่ะ"},
            format="json",
        )
        self.assertEqual(answered.status_code, 201)
        answer_id = answered.json()["id"]

        # Only the asker accepts.
        forbidden = self.client.post(
            f"/api/v1/qa/threads/{thread.pk}/accept/",
            {"answer_id": answer_id},
            format="json",
        )
        self.assertEqual(forbidden.status_code, 404)

        self.client.force_login(self.asker)
        accepted = self.client.post(
            f"/api/v1/qa/threads/{thread.pk}/accept/",
            {"answer_id": answer_id},
            format="json",
        )
        self.assertEqual(accepted.status_code, 200)
        self.assertEqual(accepted.json()["accepted_answer"]["id"], answer_id)

    def test_hidden_thread_and_its_answers_are_404(self) -> None:
        hidden = create_thread(
            author=self.asker, recipe=self.recipe, status=ThreadStatus.HIDDEN
        )
        create_answer(thread=hidden, author=self.helper)

        self.client.force_login(self.helper)
        detail = self.client.get(f"/api/v1/qa/threads/{hidden.pk}/")
        answers = self.client.get(f"/api/v1/qa/threads/{hidden.pk}/answers/")
        self.assertEqual(detail.status_code, 404)
        self.assertEqual(answers.status_code, 404)

    def test_deleted_thread_leaks_nothing(self) -> None:
        thread = create_thread(
            author=self.asker,
            recipe=self.recipe,
            title="หัวข้อลับ",
            status=ThreadStatus.DELETED,
        )
        listing = self.client.get("/api/v1/qa/threads/")
        search = self.client.get("/api/v1/qa/threads/?search=หัวข้อลับ")
        detail = self.client.get(f"/api/v1/qa/threads/{thread.pk}/")

        self.assertNotIn("หัวข้อลับ", str(listing.json()))
        self.assertEqual(search.json()["count"], 0)
        self.assertEqual(detail.status_code, 404)

    def test_stranger_cannot_edit_thread(self) -> None:
        thread = create_thread(author=self.asker, recipe=self.recipe)
        self.client.force_login(self.helper)
        response = self.client.patch(
            f"/api/v1/qa/threads/{thread.pk}/", {"title": "แอบ"}, format="json"
        )
        self.assertEqual(response.status_code, 404)

    def test_filters_and_search(self) -> None:
        create_thread(author=self.asker, recipe=self.recipe, title="ครัวซองต์ไหม้")
        other = create_published_recipe(author=self.chef, slug="qapi-other")
        create_thread(author=self.asker, recipe=other, title="คุกกี้นิ่ม")

        by_recipe = self.client.get(
            f"/api/v1/qa/threads/?recipe_id={self.recipe.id}"
        ).json()
        by_search = self.client.get("/api/v1/qa/threads/?search=คุกกี้").json()

        self.assertEqual(by_recipe["count"], 1)
        self.assertEqual(by_search["count"], 1)
        self.assertIn("คุกกี้", by_search["results"][0]["title"])

    def test_no_email_in_public_payload(self) -> None:
        thread = create_thread(author=self.asker, recipe=self.recipe)
        create_answer(thread=thread, author=self.helper)

        listing = str(self.client.get("/api/v1/qa/threads/").json())
        answers = str(
            self.client.get(f"/api/v1/qa/threads/{thread.pk}/answers/").json()
        )
        for blob in (listing, answers):
            self.assertNotIn(self.asker.email, blob)
            self.assertNotIn(self.helper.email, blob)

    def test_list_query_count_is_flat(self) -> None:
        for index in range(6):
            thread = create_thread(
                author=self.asker, recipe=self.recipe, title=f"คำถามที่ {index}"
            )
            create_answer(thread=thread, author=self.helper)
        # count + page (select_related covers author/refs/accepted).
        with self.assertNumQueries(2):
            response = self.client.get("/api/v1/qa/threads/")
        self.assertEqual(response.json()["count"], 6)

    def test_notification_failure_does_not_fail_the_answer(self) -> None:
        thread = create_thread(author=self.asker, recipe=self.recipe)
        self.client.force_login(self.helper)
        with mock.patch.object(
            Notification.objects, "create", side_effect=RuntimeError("boom")
        ):
            response = self.client.post(
                f"/api/v1/qa/threads/{thread.pk}/answers/",
                {"body": "ยังตอบได้"},
                format="json",
            )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Notification.objects.count(), 0)
