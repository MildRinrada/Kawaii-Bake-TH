"""Business logic for the XP ledger.

The XP values live **here**, not on models: they are rules, and a rule
change plus recalculation must re-derive consistently everywhere.

Everything is pull-based. Nothing in progress, certificates, quizzes or
reviews ever calls this module  recalculation reads their public fact
counts and reconciles the ledger up to them, appending only the
difference. Facts are monotonic (append-only ledgers, stamp-once
timestamps, distinct-entity counts), so reconciliation never needs to
remove anything, which is what keeps the ledger append-only and the
operation idempotent.
"""

from __future__ import annotations

import logging

from apps.certificates.selectors import certificate_selector
from apps.gamification.constants import XPReason
from apps.gamification.models import UserLevel, XPTransaction
from apps.gamification.repositories import gamification_repository
from apps.gamification.selectors import gamification_selector
from apps.gamification.services import level_service
from apps.progress.selectors import progress_selector
from apps.quizzes.selectors import attempt_selector
from apps.reviews.selectors import review_selector

logger = logging.getLogger("kawaiibake.gamification")

# The XP rules  service-owned, per the standing "rules are code" call.
XP_RULES: dict[str, int] = {
    XPReason.LESSON_COMPLETED: 10,
    XPReason.COURSE_COMPLETED: 100,
    XPReason.QUIZ_COMPLETED: 20,
    XPReason.CERTIFICATE_ISSUED: 25,
    XPReason.REVIEW_WRITTEN: 5,
}


def award(
    *,
    user_id: int,
    reason: str,
    metadata: dict | None = None,
) -> XPTransaction:
    """Append one earning event and refresh the derived level row.

    Args:
        user_id: Primary key of the user.
        reason: A value of :class:`XPReason`; fixes the points via
            :data:`XP_RULES`.
        metadata: Context for the earning event.

    Returns:
        The saved ledger entry.
    """
    entry = gamification_repository.append_xp(
        user_id=user_id,
        reason=reason,
        points=XP_RULES[reason],
        metadata=metadata,
    )
    _refresh_level(user_id=user_id)
    logger.info(
        "xp_awarded reason=%s points=%s user=%s", reason, entry.points, user_id
    )
    return entry


def recalculate(*, user_id: int) -> dict[str, int]:
    """Reconcile the ledger against the domains' current facts.

    For each reason, the expected entry count is a **derived fact count**
    read through the owning domain's public selector; missing entries are
    appended (tagged ``source: recalculate``), surplus is impossible by
    monotonicity and is left untouched regardless. Running twice appends
    nothing the second time.

    Args:
        user_id: Primary key of the user.

    Returns:
        Mapping of reason to the number of entries appended.
    """
    expected = {
        XPReason.LESSON_COMPLETED: progress_selector.completed_lesson_count(
            user_id=user_id
        ),
        XPReason.COURSE_COMPLETED: progress_selector.completed_course_count(
            user_id=user_id
        ),
        XPReason.QUIZ_COMPLETED: attempt_selector.completed_quiz_count(
            user_id=user_id
        ),
        XPReason.CERTIFICATE_ISSUED: certificate_selector.certified_course_count(
            user_id=user_id
        ),
        XPReason.REVIEW_WRITTEN: review_selector.active_review_count(
            user_id=user_id
        ),
    }
    recorded = gamification_selector.ledger_counts(user_id=user_id)

    appended: dict[str, int] = {}
    for reason, target in expected.items():
        missing = target - recorded.get(reason, 0)
        if missing <= 0:
            continue
        for _ in range(missing):
            gamification_repository.append_xp(
                user_id=user_id,
                reason=reason,
                points=XP_RULES[reason],
                metadata={"source": "recalculate"},
            )
        appended[reason] = missing

    _refresh_level(user_id=user_id)
    if appended:
        logger.info("xp_recalculated user=%s appended=%s", user_id, appended)
    return appended


def get_level(*, user_id: int) -> UserLevel:
    """The user's stored level row, deriving it on first read.

    Args:
        user_id: Primary key of the user.

    Returns:
        The level row (freshly derived if absent).
    """
    row = gamification_selector.get_user_level(user_id=user_id)
    return row if row is not None else _refresh_level(user_id=user_id)


def _refresh_level(*, user_id: int) -> UserLevel:
    """Recompute the level row from the ledger sum."""
    info = level_service.calculate_level(
        total_xp=gamification_selector.total_points(user_id=user_id)
    )
    return gamification_repository.store_level(
        user_id=user_id,
        current_level=info.level,
        current_xp=info.xp_into_level,
        total_xp=info.total_xp,
    )
