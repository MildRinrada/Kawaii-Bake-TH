"""Business logic for answers: create, edit, delete."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from apps.notifications.services import notification_service
from apps.qa.constants import ThreadStatus
from apps.qa.exceptions import AnswerNotFoundError, ThreadNotActiveError
from apps.qa.models import QuestionAnswer
from apps.qa.selectors import qa_selector
from apps.qa.services import thread_service

logger = logging.getLogger("kawaiibake.qa")


def create_answer(
    *, author_id: int, thread_id: int, data: Mapping[str, Any]
) -> QuestionAnswer:
    """Answer a visible, active thread.

    Args:
        author_id: Primary key of the answerer.
        thread_id: Primary key of the thread.
        data: Validated payload (``body``).

    Returns:
        The created answer, author preloaded.

    Raises:
        ThreadNotFoundError: If the thread is absent or hidden (404).
        ThreadNotActiveError: If visible but not open (author's own
            hidden thread)  409.
    """
    thread = thread_service.require_visible_thread(
        thread_id=thread_id, viewer_id=author_id
    )
    if thread.status != ThreadStatus.ACTIVE:
        raise ThreadNotActiveError

    answer = QuestionAnswer.objects.create(
        thread=thread, author_id=author_id, body=data["body"].strip()
    )
    logger.info(
        "qa_answer_created answer_id=%s thread_id=%s by=%s",
        answer.pk,
        thread_id,
        author_id,
    )
    if thread.author_id != author_id:
        notification_service.notify_qa_answer_received(
            thread_author_id=thread.author_id,
            answerer_handle=answer.author.username,
            thread_title=thread.title,
            thread_id=thread.pk,
        )
    return answer


def update_answer(
    *,
    answer_id: int,
    viewer_id: int,
    viewer_is_staff: bool = False,
    data: Mapping[str, Any],
) -> QuestionAnswer:
    """Edit the caller's own answer.

    Args:
        answer_id: Primary key of the answer.
        viewer_id: Primary key of the caller.
        viewer_is_staff: Whether the caller is a staff member.
        data: Validated payload (``body``).

    Returns:
        The updated answer.

    Raises:
        AnswerNotFoundError: If absent, on an invisible thread, or not
            the caller's.
    """
    answer = _require_own_answer(
        answer_id=answer_id, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )
    answer.body = data["body"].strip()
    answer.save(update_fields=["body", "updated_at"])
    return answer


def delete_answer(
    *, answer_id: int, viewer_id: int, viewer_is_staff: bool = False
) -> None:
    """Hard-delete the caller's own answer.

    If it was the accepted answer, the thread's pointer reverts to null
    at the database layer (``SET_NULL``)  no code to forget.

    Args:
        answer_id: Primary key of the answer.
        viewer_id: Primary key of the caller.
        viewer_is_staff: Whether the caller is a staff member.

    Raises:
        AnswerNotFoundError: If absent, on an invisible thread, or not
            the caller's.
    """
    answer = _require_own_answer(
        answer_id=answer_id, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )
    answer.delete()
    logger.info("qa_answer_deleted answer_id=%s by=%s", answer_id, viewer_id)


def _require_own_answer(
    *, answer_id: int, viewer_id: int, viewer_is_staff: bool
) -> QuestionAnswer:
    """An answer the caller may mutate; "not yours" is the same 404."""
    answer = qa_selector.get_answer(
        answer_id=answer_id, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )
    if answer is None or (
        answer.author_id != viewer_id and not viewer_is_staff
    ):
        raise AnswerNotFoundError
    return answer
