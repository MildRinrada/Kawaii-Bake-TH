"""Test data builders for the assistant domain."""

from __future__ import annotations

from typing import Any

from apps.assistant.constants import AssistantLanguage, ContextType, MessageRole
from apps.assistant.models import AssistantConversation, AssistantMessage

THAI_QUESTION = "วิธีทำเค้กช็อกโกแลตให้นุ่มทำอย่างไร? 🍰"
THAI_ANSWER = "ควรตีเนยกับน้ำตาลให้ขึ้นฟูก่อน แล้วอย่าอบนานเกินไปนะคะ 😊"


def create_conversation(
    *,
    user: Any,
    language: str = AssistantLanguage.TH,
    context_type: str = ContextType.GENERAL,
    prompt_version: str = "1",
    **extra: Any,
) -> AssistantConversation:
    """Create a conversation directly at the model layer."""
    return AssistantConversation.objects.create(
        user=user,
        language=language,
        context_type=context_type,
        prompt_version=prompt_version,
        **extra,
    )


def add_message(
    *,
    conversation: AssistantConversation,
    role: str = MessageRole.USER,
    content: str = THAI_QUESTION,
    **extra: Any,
) -> AssistantMessage:
    """Append a message directly at the model layer."""
    return AssistantMessage.objects.create(
        conversation=conversation, role=role, content=content, **extra
    )
