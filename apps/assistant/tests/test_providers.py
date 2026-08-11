"""Provider-boundary tests: the mock, the factory, the failure paths."""

from __future__ import annotations

from django.test import SimpleTestCase

from ai.exceptions import ProviderNotConfiguredError, UnknownProviderError
from ai.factory import build_provider
from ai.providers.mock import MockAIProvider
from ai.providers.openai import OpenAIProvider
from ai.schemas import AIMessage


class MockProviderTests(SimpleTestCase):
    """The offline default  deterministic and Thai-safe."""

    def test_echoes_the_last_user_message_in_thai(self) -> None:
        provider = MockAIProvider()
        completion = provider.generate(
            messages=[
                AIMessage(role="system", content="คุณคือผู้ช่วย"),
                AIMessage(role="user", content="ทำไมเค้กยุบตรงกลาง? 🎂"),
            ],
            language="th",
        )
        self.assertIn("ทำไมเค้กยุบตรงกลาง? 🎂", completion.content)
        self.assertTrue(completion.content.startswith("(ผู้ช่วยจำลอง)"))
        self.assertEqual(completion.model_name, "mock-1")
        self.assertGreater(completion.input_tokens, 0)
        self.assertGreater(completion.output_tokens, 0)

    def test_acknowledges_context_title(self) -> None:
        provider = MockAIProvider()
        completion = provider.generate(
            messages=[AIMessage(role="user", content="ช่วยหน่อย")],
            language="th",
            context={"title": "เค้กช็อกโกแลต"},
        )
        self.assertIn("เค้กช็อกโกแลต", completion.content)

    def test_is_deterministic(self) -> None:
        provider = MockAIProvider()
        messages = [AIMessage(role="user", content="same question")]
        first = provider.generate(messages=messages, language="en")
        second = provider.generate(messages=messages, language="en")
        self.assertEqual(first, second)


class FactoryTests(SimpleTestCase):
    """Name-based resolution."""

    def test_builds_the_mock(self) -> None:
        provider = build_provider(name="mock")
        self.assertIsInstance(provider, MockAIProvider)

    def test_builds_openai_from_config(self) -> None:
        provider = build_provider(
            name="openai", config={"api_key": "sk-test", "model": "gpt-4o-mini"}
        )
        self.assertIsInstance(provider, OpenAIProvider)

    def test_unknown_name_is_rejected(self) -> None:
        with self.assertRaises(UnknownProviderError):
            build_provider(name="skynet")


class OpenAIProviderTests(SimpleTestCase):
    """Only the offline-safe path: configuration failure."""

    def test_missing_api_key_fails_before_any_network(self) -> None:
        provider = build_provider(name="openai", config={"api_key": None})
        with self.assertRaises(ProviderNotConfiguredError):
            provider.generate(
                messages=[AIMessage(role="user", content="hi")], language="en"
            )
