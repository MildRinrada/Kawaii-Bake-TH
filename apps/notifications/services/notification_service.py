"""Business logic for creating, reading and configuring notifications.

**Delivery contract (ADR 0016).** ``notify`` registers delivery with
``transaction.on_commit``: inside a producer's atomic block it runs only
after that block commits; under plain autocommit it runs immediately 
either way, delivery can never observe (or be part of) an uncommitted
producer transaction, without any signal. Delivery itself is best-effort:
every exception inside it is logged and swallowed, so a notification
problem can never fail a review, an enrollment or an award that already
succeeded.
"""

from __future__ import annotations

import logging

from django.db import transaction
from django.utils import timezone

from apps.notifications.constants import NotificationEventType
from apps.notifications.exceptions import NotificationNotFoundError
from apps.notifications.models import Notification, NotificationPreference
from apps.notifications.selectors import notification_selector
from apps.users.selectors import user_selector

logger = logging.getLogger("kawaiibake.notifications")


def notify(
    *,
    user_id: int,
    event_type: str,
    title: str,
    body: str = "",
    actor_handle: str = "",
    link: str = "",
) -> None:
    """Queue one notification for delivery after the current transaction.

    The public entry point producers call. Returns nothing on purpose:
    delivery is asynchronous with respect to the caller's transaction and
    best-effort  producers must not branch on it.

    Args:
        user_id: Primary key of the recipient.
        event_type: A value of :class:`NotificationEventType`.
        title: Snapshot headline, rendered verbatim.
        body: Snapshot detail line.
        actor_handle: The acting user's **public handle**  never an email.
        link: Frontend path for navigation; may go stale later.
    """
    transaction.on_commit(
        lambda: _deliver(
            user_id=user_id,
            event_type=event_type,
            title=title,
            body=body,
            actor_handle=actor_handle,
            link=link,
        )
    )


def _deliver(
    *,
    user_id: int,
    event_type: str,
    title: str,
    body: str,
    actor_handle: str,
    link: str,
) -> None:
    """Create the row unless the recipient opted out. Never raises."""
    try:
        if not notification_selector.is_event_enabled(
            user_id=user_id, event_type=event_type
        ):
            return
        Notification.objects.create(
            recipient_id=user_id,
            event_type=event_type,
            title=title,
            body=body,
            actor_handle=actor_handle,
            link=link,
        )
        logger.info(
            "notification_delivered event=%s recipient=%s", event_type, user_id
        )
    except Exception:  # noqa: BLE001 - best-effort by contract (ADR 0016)
        logger.exception(
            "notification_failed event=%s recipient=%s", event_type, user_id
        )


def notify_review_received(
    *,
    owner_id: int,
    reviewer_handle: str,
    target_kind: str,
    target_title: str,
    target_slug: str,
    rating: int,
) -> None:
    """Tell a creator their recipe/course got a review.

    Args:
        owner_id: The content owner's primary key.
        reviewer_handle: The reviewer's public handle.
        target_kind: ``recipe`` or ``course`` (ReviewTargetKind values).
        target_title: Snapshot of the reviewed content's title.
        target_slug: For the frontend link.
        rating: The stars given.
    """
    kind_th = "สูตร" if target_kind == "recipe" else "คอร์ส"
    prefix = "recipes" if target_kind == "recipe" else "courses"
    notify(
        user_id=owner_id,
        event_type=NotificationEventType.REVIEW_RECEIVED,
        title=f"มีรีวิวใหม่บน{kind_th}ของคุณ",
        body=f'{reviewer_handle} ให้ {rating} ดาวกับ{kind_th} "{target_title}"',
        actor_handle=reviewer_handle,
        link=f"/{prefix}/{target_slug}/reviews/",
    )


def notify_course_enrollment(
    *,
    instructor_id: int,
    student_handle: str,
    course_title: str,
    course_slug: str,
) -> None:
    """Tell an instructor a student joined their course.

    Args:
        instructor_id: The instructor's primary key.
        student_handle: The student's public handle.
        course_title: Snapshot of the course title.
        course_slug: For the frontend link.
    """
    notify(
        user_id=instructor_id,
        event_type=NotificationEventType.COURSE_ENROLLMENT,
        title="มีนักเรียนใหม่ในคอร์สของคุณ",
        body=f'{student_handle} ลงทะเบียนเรียน "{course_title}"',
        actor_handle=student_handle,
        link=f"/courses/{course_slug}/",
    )


def notify_qa_answer_received(
    *,
    thread_author_id: int,
    answerer_handle: str,
    thread_title: str,
    thread_id: int,
) -> None:
    """Tell an asker their question got an answer.

    Args:
        thread_author_id: The question author's primary key.
        answerer_handle: The answerer's public handle.
        thread_title: Snapshot of the question title.
        thread_id: For the frontend link.
    """
    notify(
        user_id=thread_author_id,
        event_type=NotificationEventType.QA_ANSWER_RECEIVED,
        title="มีคนตอบคำถามของคุณ",
        body=f'{answerer_handle} ตอบคำถาม "{thread_title}"',
        actor_handle=answerer_handle,
        link=f"/qa/threads/{thread_id}/",
    )


def notify_qa_answer_accepted(
    *,
    answer_author_id: int,
    asker_handle: str,
    thread_title: str,
    thread_id: int,
) -> None:
    """Tell an answerer their answer was accepted.

    Args:
        answer_author_id: The answer author's primary key.
        asker_handle: The question author's public handle.
        thread_title: Snapshot of the question title.
        thread_id: For the frontend link.
    """
    notify(
        user_id=answer_author_id,
        event_type=NotificationEventType.QA_ANSWER_ACCEPTED,
        title="คำตอบของคุณถูกเลือกเป็นคำตอบที่ดีที่สุด ⭐",
        body=f'{asker_handle} เลือกคำตอบของคุณใน "{thread_title}"',
        actor_handle=asker_handle,
        link=f"/qa/threads/{thread_id}/",
    )


def notify_achievement_earned(*, user_id: int, badge_title: str) -> None:
    """Congratulate a user on a newly earned achievement.

    Args:
        user_id: The earner's primary key.
        badge_title: The badge's Thai display title.
    """
    notify(
        user_id=user_id,
        event_type=NotificationEventType.ACHIEVEMENT_EARNED,
        title="คุณได้รับความสำเร็จใหม่ 🎉",
        body=f'ปลดล็อก "{badge_title}" แล้ว',
        link="/me/achievements/",
    )


def mark_read(*, notification_id: int, user_id: int) -> Notification:
    """Stamp ``read_at`` once. Idempotent  re-reading stays successful.

    Args:
        notification_id: Primary key of the notification.
        user_id: Primary key of the caller.

    Returns:
        The (now read) notification.

    Raises:
        NotificationNotFoundError: If absent or not the caller's.
    """
    notification = notification_selector.get_owned(
        notification_id=notification_id, user_id=user_id
    )
    if notification is None:
        raise NotificationNotFoundError
    Notification.objects.filter(pk=notification.pk, read_at__isnull=True).update(
        read_at=timezone.now()
    )
    notification.refresh_from_db(fields=["read_at"])
    return notification


def mark_all_read(*, user_id: int) -> int:
    """Stamp every unread notification of the caller, in one UPDATE.

    Args:
        user_id: Primary key of the caller.

    Returns:
        How many rows this call newly marked read.
    """
    return Notification.objects.filter(
        recipient_id=user_id, read_at__isnull=True
    ).update(read_at=timezone.now())


def set_preferences(*, user_id: int, changes: dict[str, bool]) -> dict[str, bool]:
    """Upsert the caller's per-event choices.

    Only the submitted event types are touched; rows appear on first
    change (absent still means enabled).

    Args:
        user_id: Primary key of the caller.
        changes: Mapping of event type to enabled  keys already
            validated by the serializer.

    Returns:
        The full effective preference map after the update.
    """
    for event_type, enabled in changes.items():
        NotificationPreference.objects.update_or_create(
            user_id=user_id,
            event_type=event_type,
            defaults={"enabled": enabled},
        )
    return notification_selector.effective_preferences(user_id=user_id)


def broadcast_announcement(
    *, actor_id: int, title: str, body: str = "", link: str = ""
) -> int:
    """Deliver one announcement to every active account, at once.

    The one staff-produced notification (ADR 0028). It respects the same
    per-event opt-out as every machine-produced type, and it is a single
    ``bulk_create`` rather than N ``notify`` calls - a platform-sized
    audience must not schedule a platform-sized pile of on-commit
    closures.

    Args:
        actor_id: The staff member sending the announcement.
        title: Headline, rendered verbatim.
        body: Detail line.
        link: Optional frontend path.

    Returns:
        How many recipients the announcement was created for.
    """
    opted_out = set(
        NotificationPreference.objects.filter(
            event_type=NotificationEventType.ANNOUNCEMENT, enabled=False
        ).values_list("user_id", flat=True)
    )
    recipients = [
        user_id
        for user_id in user_selector.active_user_ids()
        if user_id not in opted_out
    ]
    Notification.objects.bulk_create(
        [
            Notification(
                recipient_id=user_id,
                event_type=NotificationEventType.ANNOUNCEMENT,
                title=title,
                body=body,
                link=link,
            )
            for user_id in recipients
        ],
        batch_size=500,
    )
    logger.info(
        "announcement broadcast",
        extra={"actor_id": actor_id, "recipients": len(recipients)},
    )
    return len(recipients)
