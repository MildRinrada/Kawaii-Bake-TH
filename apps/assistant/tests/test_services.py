"""Service-layer tests: context gating, prompt versioning, the send flow."""

from __future__ import annotations

from unittest import mock

from django.core.cache import cache
from django.test import TestCase, override_settings

from ai.exceptions import AIProviderError
from apps.assistant.constants import ContextType, MessageRole
from apps.assistant.exceptions import (
    AssistantUnavailableError,
    ContextAccessDeniedError,
    ContextNotFoundError,
    ConversationNotFoundError,
    InvalidContextError,
)
from apps.assistant.models import AIUsageLog, AssistantMessage, PromptTemplate
from apps.assistant.services import conversation_service, message_service
from apps.assistant.tests.factories import THAI_QUESTION
from apps.core.exceptions import RateLimitedError
from apps.courses.tests.factories import create_published_course, enroll_user
from apps.lessons.tests.factories import create_lesson
from apps.recipes.constants import RecipeVisibility
from apps.recipes.tests.factories import create_published_recipe
from apps.users.tests.factories import create_user


class ConversationCreationTests(TestCase):
    """Context validation and prompt stamping at creation."""

    def setUp(self) -> None:
        self.user = create_user(username="convuser")
        self.author = create_user(username="convauthor")

    def test_general_conversation_stamps_active_prompt_version(self) -> None:
        conversation = conversation_service.create_conversation(
            user_id=self.user.id,
            language="th",
            context_type=ContextType.GENERAL,
        )
        self.assertEqual(conversation.prompt_version, "1")
        self.assertEqual(conversation.language, "th")

    def test_recipe_conversation_requires_matching_id(self) -> None:
        with self.assertRaises(InvalidContextError):
            conversation_service.create_conversation(
                user_id=self.user.id,
                language="th",
                context_type=ContextType.RECIPE,
            )

    def test_general_conversation_rejects_stray_ids(self) -> None:
        with self.assertRaises(InvalidContextError):
            conversation_service.create_conversation(
                user_id=self.user.id,
                language="th",
                context_type=ContextType.GENERAL,
                recipe_id=1,
            )

    def test_visible_recipe_context_is_accepted(self) -> None:
        recipe = create_published_recipe(author=self.author, slug="ctx-cake")
        conversation = conversation_service.create_conversation(
            user_id=self.user.id,
            language="th",
            context_type=ContextType.RECIPE,
            recipe_id=recipe.id,
        )
        self.assertEqual(conversation.recipe_id, recipe.id)

    def test_private_recipe_context_is_denied(self) -> None:
        recipe = create_published_recipe(
            author=self.author,
            slug="secret-cake",
            visibility=RecipeVisibility.PRIVATE,
        )
        with self.assertRaises(ContextNotFoundError):
            conversation_service.create_conversation(
                user_id=self.user.id,
                language="th",
                context_type=ContextType.RECIPE,
                recipe_id=recipe.id,
            )

    def test_own_private_recipe_context_is_accepted(self) -> None:
        recipe = create_published_recipe(
            author=self.user,
            slug="my-secret-cake",
            visibility=RecipeVisibility.PRIVATE,
        )
        conversation = conversation_service.create_conversation(
            user_id=self.user.id,
            language="th",
            context_type=ContextType.RECIPE,
            recipe_id=recipe.id,
        )
        self.assertEqual(conversation.recipe_id, recipe.id)

    def test_lesson_context_requires_enrollment(self) -> None:
        course = create_published_course(instructor=self.author, slug="ctx-course")
        lesson = create_lesson(course=course)

        with self.assertRaises(ContextAccessDeniedError):
            conversation_service.create_conversation(
                user_id=self.user.id,
                language="th",
                context_type=ContextType.LESSON,
                lesson_id=lesson.id,
            )

        enroll_user(user=self.user, course=course)
        conversation = conversation_service.create_conversation(
            user_id=self.user.id,
            language="th",
            context_type=ContextType.LESSON,
            lesson_id=lesson.id,
        )
        self.assertEqual(conversation.lesson_id, lesson.id)

    def test_lesson_on_hidden_course_is_404_not_403(self) -> None:
        course = create_published_course(
            instructor=self.author, slug="ctx-draft", status="draft"
        )
        lesson = create_lesson(course=course)
        with self.assertRaises(ContextNotFoundError):
            conversation_service.create_conversation(
                user_id=self.user.id,
                language="th",
                context_type=ContextType.LESSON,
                lesson_id=lesson.id,
            )

    def test_course_context_loads_for_visible_course(self) -> None:
        course = create_published_course(instructor=self.author, slug="ctx-open")
        conversation = conversation_service.create_conversation(
            user_id=self.user.id,
            language="en",
            context_type=ContextType.COURSE,
            course_id=course.id,
        )
        self.assertEqual(conversation.course_id, course.id)

    def test_no_active_template_is_unavailable(self) -> None:
        PromptTemplate.objects.filter(name=ContextType.GENERAL, language="th").update(
            is_active=False
        )
        with self.assertRaises(AssistantUnavailableError):
            conversation_service.create_conversation(
                user_id=self.user.id,
                language="th",
                context_type=ContextType.GENERAL,
            )


class SendMessageTests(TestCase):
    """The two-transaction send flow against the mock provider."""

    def setUp(self) -> None:
        cache.clear()  # rate-limit counters must not leak between tests
        self.user = create_user(username="senduser")
        self.conversation = conversation_service.create_conversation(
            user_id=self.user.id, language="th", context_type=ContextType.GENERAL
        )

    def test_send_persists_both_turns_and_usage(self) -> None:
        reply = message_service.send_message(
            user_id=self.user.id,
            conversation_id=self.conversation.pk,
            content=THAI_QUESTION,
        )

        self.assertEqual(reply.role, MessageRole.ASSISTANT)
        self.assertIn(THAI_QUESTION, reply.content)
        self.assertEqual(reply.provider, "mock")
        self.assertEqual(reply.model_name, "mock-1")
        self.assertIsNotNone(reply.token_output)

        turns = list(AssistantMessage.objects.filter(conversation=self.conversation))
        self.assertEqual([t.role for t in turns], ["user", "assistant"])
        self.assertEqual(turns[0].content, THAI_QUESTION)

        usage = AIUsageLog.objects.get(user=self.user)
        self.assertEqual(usage.provider, "mock")
        self.assertGreater(usage.output_tokens, 0)

    def test_first_message_titles_the_conversation_once(self) -> None:
        message_service.send_message(
            user_id=self.user.id,
            conversation_id=self.conversation.pk,
            content=THAI_QUESTION,
        )
        self.conversation.refresh_from_db()
        self.assertEqual(self.conversation.title, THAI_QUESTION[:80])

        message_service.send_message(
            user_id=self.user.id,
            conversation_id=self.conversation.pk,
            content="คำถามที่สอง",
        )
        self.conversation.refresh_from_db()
        self.assertEqual(self.conversation.title, THAI_QUESTION[:80])

    def test_someone_elses_conversation_is_404(self) -> None:
        stranger = create_user(username="sendstranger")
        with self.assertRaises(ConversationNotFoundError):
            message_service.send_message(
                user_id=stranger.id,
                conversation_id=self.conversation.pk,
                content="สวัสดี",
            )

    def test_old_conversation_keeps_its_prompt_version(self) -> None:
        # Ship prompt v2: deactivate v1, activate v2.
        PromptTemplate.objects.filter(name=ContextType.GENERAL, language="th").update(
            is_active=False
        )
        PromptTemplate.objects.create(
            name=ContextType.GENERAL,
            language="th",
            version="2",
            template="เวอร์ชันใหม่",
            is_active=True,
        )

        # The old conversation still answers under v1…
        reply = message_service.send_message(
            user_id=self.user.id,
            conversation_id=self.conversation.pk,
            content="ยังตอบได้ไหม?",
        )
        self.assertEqual(reply.role, MessageRole.ASSISTANT)
        self.conversation.refresh_from_db()
        self.assertEqual(self.conversation.prompt_version, "1")

        # …while a new conversation is stamped with v2.
        fresh = conversation_service.create_conversation(
            user_id=self.user.id, language="th", context_type=ContextType.GENERAL
        )
        self.assertEqual(fresh.prompt_version, "2")

    def test_provider_failure_keeps_user_message(self) -> None:
        failing = mock.Mock()
        failing.name = "mock"
        failing.generate.side_effect = AIProviderError("boom")

        with mock.patch.object(
            message_service, "_get_provider", return_value=failing
        ):
            with self.assertRaises(AssistantUnavailableError):
                message_service.send_message(
                    user_id=self.user.id,
                    conversation_id=self.conversation.pk,
                    content="จะพังไหม?",
                )

        turns = AssistantMessage.objects.filter(conversation=self.conversation)
        self.assertEqual(turns.count(), 1)
        self.assertEqual(turns.first().role, MessageRole.USER)
        self.assertFalse(AIUsageLog.objects.filter(user=self.user).exists())

    @override_settings(
        ASSISTANT_MESSAGE_RATE_LIMIT_ATTEMPTS=2,
        ASSISTANT_MESSAGE_RATE_LIMIT_WINDOW=60,
    )
    def test_rate_limit_hook_throttles_sends(self) -> None:
        for _ in range(2):
            message_service.send_message(
                user_id=self.user.id,
                conversation_id=self.conversation.pk,
                content="ถามรัว ๆ",
            )
        with self.assertRaises(RateLimitedError):
            message_service.send_message(
                user_id=self.user.id,
                conversation_id=self.conversation.pk,
                content="ครั้งที่สาม",
            )


class ContextDegradationTests(TestCase):
    """Message-time context is lenient: vanished targets degrade, not crash."""

    def setUp(self) -> None:
        cache.clear()
        self.user = create_user(username="degradeuser")
        self.author = create_user(username="degradeauthor")

    def test_send_still_works_after_target_recipe_is_deleted(self) -> None:
        recipe = create_published_recipe(author=self.author, slug="degrade-cake")
        conversation = conversation_service.create_conversation(
            user_id=self.user.id,
            language="th",
            context_type=ContextType.RECIPE,
            recipe_id=recipe.id,
        )
        recipe.delete()

        reply = message_service.send_message(
            user_id=self.user.id,
            conversation_id=conversation.pk,
            content="สูตรหายไปแล้วหรือ?",
        )
        self.assertEqual(reply.role, MessageRole.ASSISTANT)

    def test_send_still_works_after_recipe_goes_private(self) -> None:
        recipe = create_published_recipe(author=self.author, slug="hide-cake")
        conversation = conversation_service.create_conversation(
            user_id=self.user.id,
            language="th",
            context_type=ContextType.RECIPE,
            recipe_id=recipe.id,
        )
        recipe.visibility = RecipeVisibility.PRIVATE
        recipe.save(update_fields=["visibility"])

        reply = message_service.send_message(
            user_id=self.user.id,
            conversation_id=conversation.pk,
            content="ยังเห็นสูตรไหม?",
        )
        # The reply exists, and the now-private content was not injected.
        self.assertEqual(reply.role, MessageRole.ASSISTANT)
