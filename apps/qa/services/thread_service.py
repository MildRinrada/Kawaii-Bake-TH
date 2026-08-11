"""Business logic for question threads: create, edit, moderate, accept."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from apps.courses.selectors import course_selector
from apps.notifications.services import notification_service
from apps.qa.constants import ThreadStatus, ThreadTargetKind
from apps.qa.exceptions import (
    InvalidAcceptError,
    ModerationNotAllowedError,
    ThreadNotActiveError,
    ThreadNotFoundError,
    ThreadTargetNotFoundError,
)
from apps.qa.models import QuestionThread
from apps.qa.selectors import qa_selector
from apps.recipes.selectors import recipe_selector

logger = logging.getLogger("kawaiibake.qa")


def create_thread(
    *, author_id: int, kind: str, slug: str, data: Mapping[str, Any]
) -> QuestionThread:
    """Ask a question about a visible recipe or course.

    Args:
        author_id: Primary key of the asker.
        kind: A value of :class:`ThreadTargetKind`.
        slug: The target's slug.
        data: Validated payload (``title``, optional ``body``).

    Returns:
        The created thread, relations preloaded.

    Raises:
        ThreadTargetNotFoundError: If the target is absent or hidden.
    """
    target_id = _resolve_target(kind=kind, slug=slug, viewer_id=author_id)
    thread = QuestionThread.objects.create(
        author_id=author_id,
        recipe_id=target_id if kind == ThreadTargetKind.RECIPE else None,
        course_id=target_id if kind == ThreadTargetKind.COURSE else None,
        title=data["title"].strip(),
        body=(data.get("body") or "").strip(),
    )
    logger.info(
        "qa_thread_created thread_id=%s %s_id=%s by=%s",
        thread.pk,
        kind,
        target_id,
        author_id,
    )
    return _reload(thread_id=thread.pk, viewer_id=author_id)


def update_thread(
    *,
    thread_id: int,
    viewer_id: int,
    viewer_is_staff: bool = False,
    data: Mapping[str, Any],
) -> QuestionThread:
    """Edit a thread (author) and/or change its status (staff).

    Args:
        thread_id: Primary key of the thread.
        viewer_id: Primary key of the caller.
        viewer_is_staff: Whether the caller is a staff member.
        data: Validated payload; absent keys are unchanged.

    Returns:
        The updated thread.

    Raises:
        ThreadNotFoundError: If absent, deleted, or not addressable.
        ModerationNotAllowedError: If a non-staff caller sends ``status``.
    """
    thread = _require_manageable(
        thread_id=thread_id, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )

    if "status" in data:
        if not viewer_is_staff:
            raise ModerationNotAllowedError
        thread.status = data["status"]
        thread.save(update_fields=["status", "updated_at"])
        logger.info(
            "qa_thread_moderated thread_id=%s status=%s by=%s",
            thread.pk,
            data["status"],
            viewer_id,
        )

    updates = []
    for field in ("title", "body"):
        if field in data:
            setattr(thread, field, data[field].strip())
            updates.append(field)
    if updates:
        thread.save(update_fields=[*updates, "updated_at"])
    return _reload(
        thread_id=thread.pk, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )


def delete_thread(
    *, thread_id: int, viewer_id: int, viewer_is_staff: bool = False
) -> None:
    """Soft-delete a thread  it vanishes from every API surface.

    The row and its answers survive as history (other users' words are
    not the asker's to destroy), but no endpoint returns them again.

    Args:
        thread_id: Primary key of the thread.
        viewer_id: Primary key of the caller.
        viewer_is_staff: Whether the caller is a staff member.

    Raises:
        ThreadNotFoundError: If absent, deleted, or not addressable.
    """
    thread = _require_manageable(
        thread_id=thread_id, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )
    thread.status = ThreadStatus.DELETED
    thread.save(update_fields=["status", "updated_at"])
    logger.info("qa_thread_deleted thread_id=%s by=%s", thread_id, viewer_id)


def accept_answer(
    *,
    thread_id: int,
    answer_id: int,
    viewer_id: int,
    viewer_is_staff: bool = False,
) -> QuestionThread:
    """Mark one answer as accepted  at most one per thread.

    A single-field UPDATE: the previous accepted answer is unset by the
    same write, because one column cannot point at two rows.

    Args:
        thread_id: Primary key of the thread.
        answer_id: Primary key of the accepted answer.
        viewer_id: Primary key of the caller (thread author or staff).
        viewer_is_staff: Whether the caller is a staff member.

    Returns:
        The updated thread.

    Raises:
        ThreadNotFoundError: If absent, deleted, or not addressable.
        ThreadNotActiveError: If the thread is not open.
        InvalidAcceptError: If the answer belongs to another thread.
    """
    thread = _require_manageable(
        thread_id=thread_id, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )
    if thread.status != ThreadStatus.ACTIVE:
        raise ThreadNotActiveError

    answer = thread.answers.filter(pk=answer_id).select_related("author").first()
    if answer is None:
        raise InvalidAcceptError

    changed = thread.accepted_answer_id != answer.pk
    thread.accepted_answer = answer
    thread.save(update_fields=["accepted_answer", "updated_at"])
    logger.info(
        "qa_answer_accepted thread_id=%s answer_id=%s by=%s",
        thread_id,
        answer_id,
        viewer_id,
    )

    if changed and answer.author_id != thread.author_id:
        notification_service.notify_qa_answer_accepted(
            answer_author_id=answer.author_id,
            asker_handle=thread.author.username,
            thread_title=thread.title,
            thread_id=thread.pk,
        )
    return _reload(
        thread_id=thread.pk, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )


def require_visible_thread(
    *, thread_id: int, viewer_id: int | None, viewer_is_staff: bool = False
) -> QuestionThread:
    """Fetch a thread the viewer may read, or 404.

    Args:
        thread_id: Primary key of the thread.
        viewer_id: Primary key of the viewer, or ``None`` when anonymous.
        viewer_is_staff: Whether the viewer is a staff member.

    Returns:
        The thread.

    Raises:
        ThreadNotFoundError: If absent, deleted, or hidden from view.
    """
    thread = qa_selector.get_thread(
        thread_id=thread_id, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )
    if thread is None:
        raise ThreadNotFoundError
    return thread


def _resolve_target(*, kind: str, slug: str, viewer_id: int) -> int:
    """Resolve the asked-about content through its public ref selector."""
    if kind == ThreadTargetKind.RECIPE:
        recipe = recipe_selector.get_recipe_ref(slug=slug, viewer_id=viewer_id)
        if recipe is None:
            raise ThreadTargetNotFoundError
        return recipe.id
    course = course_selector.get_course_ref(slug=slug, viewer_id=viewer_id)
    if course is None:
        raise ThreadTargetNotFoundError
    return course.id


def _require_manageable(
    *, thread_id: int, viewer_id: int, viewer_is_staff: bool
) -> QuestionThread:
    """A visible thread the caller may manage; "not yours" is the same 404."""
    thread = require_visible_thread(
        thread_id=thread_id, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )
    if thread.author_id != viewer_id and not viewer_is_staff:
        raise ThreadNotFoundError
    return thread


def _reload(
    *, thread_id: int, viewer_id: int, viewer_is_staff: bool = False
) -> QuestionThread:
    """Re-read with relations for serialization."""
    thread = qa_selector.get_thread(
        thread_id=thread_id, viewer_id=viewer_id, viewer_is_staff=viewer_is_staff
    )
    if thread is None:  # pragma: no cover - vanished between write and read
        raise ThreadNotFoundError
    return thread
