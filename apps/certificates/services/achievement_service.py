"""Business logic for awarding achievements.

Awards are pulled by this app from public facts (progress counts), never
pushed by content apps and never wired to model signals — future
achievement sources call :func:`award` or extend :func:`recalculate`.
"""

from __future__ import annotations

import logging

from django.db.models import QuerySet

from apps.certificates.constants import TEN_COURSES_THRESHOLD, AchievementType
from apps.certificates.models import Achievement
from apps.certificates.repositories import certificate_repository
from apps.certificates.selectors import certificate_selector
from apps.notifications.services import notification_service
from apps.progress.selectors import progress_selector

logger = logging.getLogger("kawaiibake.certificates")


def award(
    *, user_id: int, achievement_type: str, metadata: dict | None = None
) -> tuple[Achievement, bool]:
    """Record an achievement, idempotently.

    The public entry point future phases call — quiz/recipe awards will
    arrive here via ``recalculate``, reading those apps' public selectors.

    Args:
        user_id: Primary key of the user.
        achievement_type: A value of :class:`AchievementType`.
        metadata: Context for the earning event.

    Returns:
        The achievement and whether this call created it.
    """
    achievement, created = certificate_repository.award_achievement(
        user_id=user_id, achievement_type=achievement_type, metadata=metadata
    )
    if created:
        logger.info(
            "achievement_awarded type=%s user=%s", achievement_type, user_id
        )
        badge_title = (
            achievement.badge.title_th
            if achievement.badge is not None
            else str(AchievementType(achievement_type).label)
        )
        # First earning only; best-effort, post-commit (ADR 0016) — a
        # notification problem never fails the award.
        notification_service.notify_achievement_earned(
            user_id=user_id, badge_title=badge_title
        )
    return achievement, created


def award_course_achievements(
    *, user_id: int, course_id: int, course_title: str
) -> list[Achievement]:
    """Award everything a course completion can trigger.

    Called by certificate issuance. Volume thresholds read progress'
    completed-course count — the stamped facts, computed live.

    Args:
        user_id: Primary key of the user.
        course_id: The completed course.
        course_title: Snapshot for the metadata.

    Returns:
        The newly awarded achievements (empty when all were already held).
    """
    awarded: list[Achievement] = []
    context = {"course_id": course_id, "course_title": course_title}

    for achievement_type in (
        AchievementType.COURSE_COMPLETED,
        AchievementType.FIRST_COURSE,
    ):
        achievement, created = award(
            user_id=user_id, achievement_type=achievement_type, metadata=context
        )
        if created:
            awarded.append(achievement)

    completed = progress_selector.completed_course_count(user_id=user_id)
    if completed >= TEN_COURSES_THRESHOLD:
        achievement, created = award(
            user_id=user_id,
            achievement_type=AchievementType.TEN_COURSES,
            metadata={"completed_courses": completed},
        )
        if created:
            awarded.append(achievement)
    return awarded


def list_user(*, user_id: int) -> QuerySet[Achievement]:
    """The user's earned achievements, badges preloaded.

    Args:
        user_id: Primary key of the caller.

    Returns:
        A lazy queryset, newest first.
    """
    return certificate_selector.list_achievements_for_user(user_id=user_id)


def recalculate(*, user_id: int) -> list[Achievement]:
    """Re-derive derivable achievements from current facts.

    Append-only repair: awards anything the facts now justify, removes
    nothing. Today that covers the course-volume family; quiz/recipe
    achievements join here (reading those apps' public selectors) in a
    future phase.

    Args:
        user_id: Primary key of the user.

    Returns:
        The newly awarded achievements.
    """
    awarded: list[Achievement] = []
    completed = progress_selector.completed_course_count(user_id=user_id)
    if completed < 1:
        return awarded

    held = certificate_selector.earned_types(user_id=user_id)
    for achievement_type, metadata in (
        (AchievementType.COURSE_COMPLETED, {"completed_courses": completed}),
        (AchievementType.FIRST_COURSE, {"completed_courses": completed}),
    ):
        if achievement_type not in held:
            achievement, created = award(
                user_id=user_id,
                achievement_type=achievement_type,
                metadata=metadata,
            )
            if created:
                awarded.append(achievement)

    if (
        completed >= TEN_COURSES_THRESHOLD
        and AchievementType.TEN_COURSES not in held
    ):
        achievement, created = award(
            user_id=user_id,
            achievement_type=AchievementType.TEN_COURSES,
            metadata={"completed_courses": completed},
        )
        if created:
            awarded.append(achievement)
    return awarded
