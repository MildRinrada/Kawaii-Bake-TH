"""Test data builders for the Q&A domain."""

from __future__ import annotations

from typing import Any

from apps.qa.constants import ThreadStatus
from apps.qa.models import QuestionAnswer, QuestionThread

THAI_QUESTION_TITLE = "ทำไมครัวซองต์ไม่ขึ้นชั้น?"
THAI_ANSWER_BODY = "เนยอาจละลายตอนพับแป้ง ลองแช่เย็นระหว่างพับทุกรอบนะคะ 🥐"


def create_thread(
    *,
    author: Any,
    recipe: Any = None,
    course: Any = None,
    title: str = THAI_QUESTION_TITLE,
    status: str = ThreadStatus.ACTIVE,
    **extra: Any,
) -> QuestionThread:
    """Create a thread directly at the model layer."""
    return QuestionThread.objects.create(
        author=author,
        recipe=recipe,
        course=course,
        title=title,
        body=extra.pop("body", "พับสามรอบตามสูตรแล้วค่ะ"),
        status=status,
        **extra,
    )


def create_answer(
    *, thread: QuestionThread, author: Any, body: str = THAI_ANSWER_BODY
) -> QuestionAnswer:
    """Create an answer directly at the model layer."""
    return QuestionAnswer.objects.create(thread=thread, author=author, body=body)
