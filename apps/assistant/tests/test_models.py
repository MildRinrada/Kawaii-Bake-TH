"""Model-layer tests: Thai persistence, constraints, seeded templates."""

from __future__ import annotations

from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.assistant.constants import AssistantLanguage, ContextType, MessageRole
from apps.assistant.models import AssistantMessage, PromptTemplate
from apps.assistant.tests.factories import (
    THAI_ANSWER,
    THAI_QUESTION,
    add_message,
    create_conversation,
)
from apps.recipes.tests.factories import create_published_recipe
from apps.users.tests.factories import create_user


class ThaiPersistenceTests(TestCase):
    """Thai text and emoji must survive the database byte-perfect."""

    def setUp(self) -> None:
        self.user = create_user(username="thaiuser")

    def test_thai_message_round_trip(self) -> None:
        conversation = create_conversation(user=self.user)
        add_message(conversation=conversation, content=THAI_QUESTION)
        add_message(
            conversation=conversation,
            role=MessageRole.ASSISTANT,
            content=THAI_ANSWER,
        )

        stored = list(AssistantMessage.objects.filter(conversation=conversation))
        self.assertEqual(stored[0].content, THAI_QUESTION)
        self.assertEqual(stored[1].content, THAI_ANSWER)

    def test_multiline_text_with_emoji_survives(self) -> None:
        content = "บรรทัดแรก 🧁\nบรรทัดที่สอง!?\n\nย่อหน้าใหม่ ครับ/ค่ะ 🎂✨"
        conversation = create_conversation(user=self.user)
        message = add_message(conversation=conversation, content=content)

        message.refresh_from_db()
        self.assertEqual(message.content, content)

    def test_thai_conversation_title_round_trip(self) -> None:
        conversation = create_conversation(
            user=self.user, title="ปรึกษาเรื่องเค้กยุบตรงกลาง"
        )
        conversation.refresh_from_db()
        self.assertEqual(conversation.title, "ปรึกษาเรื่องเค้กยุบตรงกลาง")


class ConversationConstraintTests(TestCase):
    """The context check constraint and prompt-version stamping."""

    def setUp(self) -> None:
        self.user = create_user(username="constraintuser")

    def test_general_conversation_rejects_a_target(self) -> None:
        recipe = create_published_recipe(author=self.user, slug="constraint-cake")
        with self.assertRaises(IntegrityError), transaction.atomic():
            create_conversation(
                user=self.user,
                context_type=ContextType.GENERAL,
                recipe=recipe,
            )

    def test_recipe_conversation_rejects_a_foreign_target(self) -> None:
        # A lesson id on a recipe conversation violates the shape constraint.
        from apps.courses.tests.factories import create_published_course
        from apps.lessons.tests.factories import create_lesson

        course = create_published_course(instructor=self.user, slug="c-shape")
        lesson = create_lesson(course=course)
        with self.assertRaises(IntegrityError), transaction.atomic():
            create_conversation(
                user=self.user,
                context_type=ContextType.RECIPE,
                lesson=lesson,
            )

    def test_typed_conversation_survives_target_deletion(self) -> None:
        recipe = create_published_recipe(author=self.user, slug="doomed-cake")
        conversation = create_conversation(
            user=self.user, context_type=ContextType.RECIPE, recipe=recipe
        )
        add_message(conversation=conversation)

        recipe.delete()

        conversation.refresh_from_db()
        self.assertIsNone(conversation.recipe_id)
        self.assertEqual(conversation.messages.count(), 1)

    def test_prompt_version_is_stored_per_conversation(self) -> None:
        conversation = create_conversation(user=self.user, prompt_version="7")
        conversation.refresh_from_db()
        self.assertEqual(conversation.prompt_version, "7")


class PromptTemplateTests(TestCase):
    """Seeded rows and the one-active-per-(name, language) rule."""

    def test_migration_seeded_all_context_language_pairs(self) -> None:
        pairs = set(
            PromptTemplate.objects.filter(is_active=True).values_list(
                "name", "language"
            )
        )
        expected = {
            (context, language)
            for context in ContextType.values
            for language in AssistantLanguage.values
        }
        self.assertEqual(pairs, expected)

    def test_second_active_version_is_rejected(self) -> None:
        with self.assertRaises(IntegrityError), transaction.atomic():
            PromptTemplate.objects.create(
                name=ContextType.GENERAL,
                language=AssistantLanguage.TH,
                version="2",
                template="ใหม่",
                is_active=True,
            )

    def test_inactive_new_version_coexists(self) -> None:
        row = PromptTemplate.objects.create(
            name=ContextType.GENERAL,
            language=AssistantLanguage.TH,
            version="2",
            template="ใหม่",
            is_active=False,
        )
        self.assertFalse(row.is_active)
