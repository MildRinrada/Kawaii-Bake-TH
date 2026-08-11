"""API tests: the endpoint surface, ownership, Thai round-trip, no N+1."""

from __future__ import annotations

from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from apps.assistant.constants import ContextType
from apps.assistant.services import conversation_service, message_service
from apps.assistant.tests.factories import THAI_QUESTION
from apps.recipes.tests.factories import create_published_recipe
from apps.users.tests.factories import create_user


class AssistantApiTests(TestCase):
    """The four endpoints end to end against the mock provider."""

    def setUp(self) -> None:
        cache.clear()
        self.client = APIClient()
        self.user = create_user(username="apiuser")
        self.stranger = create_user(username="apistranger")

    def test_anonymous_is_denied_everywhere(self) -> None:
        conversation = conversation_service.create_conversation(
            user_id=self.user.id, language="th", context_type=ContextType.GENERAL
        )
        paths = [
            ("post", "/api/v1/assistant/conversations/"),
            ("get", f"/api/v1/assistant/conversations/{conversation.pk}/"),
            ("post", f"/api/v1/assistant/conversations/{conversation.pk}/messages/"),
            ("get", "/api/v1/me/assistant/conversations/"),
        ]
        for method, path in paths:
            with self.subTest(path=path):
                response = getattr(self.client, method)(path)
                self.assertEqual(response.status_code, 401)

    def test_create_conversation_returns_the_object(self) -> None:
        self.client.force_login(self.user)
        response = self.client.post(
            "/api/v1/assistant/conversations/",
            {"language": "th", "context_type": "general"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body["language"], "th")
        self.assertEqual(body["context_type"], "general")
        self.assertEqual(body["prompt_version"], "1")
        self.assertIsNone(body["recipe_id"])

    def test_create_with_recipe_context(self) -> None:
        author = create_user(username="apiauthor")
        recipe = create_published_recipe(author=author, slug="api-cake")
        self.client.force_login(self.user)
        response = self.client.post(
            "/api/v1/assistant/conversations/",
            {"language": "th", "context_type": "recipe", "recipe_id": recipe.id},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["recipe_id"], recipe.id)

    def test_mismatched_context_ids_are_400(self) -> None:
        self.client.force_login(self.user)
        response = self.client.post(
            "/api/v1/assistant/conversations/",
            {"language": "th", "context_type": "recipe"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "invalid_context")

    def test_unknown_keys_are_rejected(self) -> None:
        self.client.force_login(self.user)
        response = self.client.post(
            "/api/v1/assistant/conversations/",
            {"language": "th", "contextType": "general"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_thai_message_round_trip_through_http(self) -> None:
        self.client.force_login(self.user)
        conversation = self.client.post(
            "/api/v1/assistant/conversations/", {"language": "th"}, format="json"
        ).json()

        sent = self.client.post(
            f"/api/v1/assistant/conversations/{conversation['id']}/messages/",
            {"content": THAI_QUESTION},
            format="json",
        )
        self.assertEqual(sent.status_code, 201)
        reply = sent.json()
        self.assertEqual(reply["role"], "assistant")
        # The mock echoes  the exact Thai bytes must come back unchanged.
        self.assertIn(THAI_QUESTION, reply["content"])

        history = self.client.get(
            f"/api/v1/assistant/conversations/{conversation['id']}/"
        ).json()
        contents = [m["content"] for m in history["messages"]["results"]]
        self.assertEqual(contents[0], THAI_QUESTION)

    def test_history_shape_and_pagination(self) -> None:
        self.client.force_login(self.user)
        conversation = conversation_service.create_conversation(
            user_id=self.user.id, language="th", context_type=ContextType.GENERAL
        )
        for index in range(3):
            message_service.send_message(
                user_id=self.user.id,
                conversation_id=conversation.pk,
                content=f"คำถามที่ {index}",
            )

        response = self.client.get(
            f"/api/v1/assistant/conversations/{conversation.pk}/?page_size=4"
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["conversation"]["id"], conversation.pk)
        self.assertEqual(body["messages"]["count"], 6)
        self.assertIsNotNone(body["messages"]["next"])
        self.assertEqual(len(body["messages"]["results"]), 4)
        # Chronological: the transcript starts with the first user turn.
        self.assertEqual(body["messages"]["results"][0]["content"], "คำถามที่ 0")

    def test_message_over_the_cap_is_400(self) -> None:
        self.client.force_login(self.user)
        conversation = conversation_service.create_conversation(
            user_id=self.user.id, language="th", context_type=ContextType.GENERAL
        )
        response = self.client.post(
            f"/api/v1/assistant/conversations/{conversation.pk}/messages/",
            {"content": "ก" * 4001},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_someone_elses_conversation_is_404(self) -> None:
        conversation = conversation_service.create_conversation(
            user_id=self.user.id, language="th", context_type=ContextType.GENERAL
        )
        self.client.force_login(self.stranger)

        detail = self.client.get(
            f"/api/v1/assistant/conversations/{conversation.pk}/"
        )
        send = self.client.post(
            f"/api/v1/assistant/conversations/{conversation.pk}/messages/",
            {"content": "แอบดู"},
            format="json",
        )
        self.assertEqual(detail.status_code, 404)
        self.assertEqual(send.status_code, 404)

    def test_my_conversations_lists_only_mine(self) -> None:
        mine = conversation_service.create_conversation(
            user_id=self.user.id, language="th", context_type=ContextType.GENERAL
        )
        conversation_service.create_conversation(
            user_id=self.stranger.id, language="en", context_type=ContextType.GENERAL
        )
        self.client.force_login(self.user)

        response = self.client.get("/api/v1/me/assistant/conversations/")
        body = response.json()
        self.assertEqual(body["count"], 1)
        self.assertEqual(body["results"][0]["id"], mine.pk)

    def test_history_query_count_is_flat(self) -> None:
        self.client.force_login(self.user)
        conversation = conversation_service.create_conversation(
            user_id=self.user.id, language="th", context_type=ContextType.GENERAL
        )
        for index in range(8):
            message_service.send_message(
                user_id=self.user.id,
                conversation_id=conversation.pk,
                content=f"คำถามที่ {index}",
            )

        # session + user + conversation + count + page  flat regardless of
        # transcript length.
        with self.assertNumQueries(5):
            response = self.client.get(
                f"/api/v1/assistant/conversations/{conversation.pk}/"
            )
        self.assertEqual(response.json()["messages"]["count"], 16)
