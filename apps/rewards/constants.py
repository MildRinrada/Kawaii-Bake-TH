"""Constants and the reward rule registry.

Every reward amount and every user-facing reason text lives here  the
``XP_RULES`` discipline (ADR 0015): changing the economy is a reviewable
one-file diff, and reconciliation re-derives consistently everywhere.

Thai is first-class: a reason is a stable machine code plus a Thai and an
English title. The code is what the ledger stores; the titles are what
users see. Thai is authored text, never a fallback translation.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.db import models


class RewardKind(models.TextChoices):
    """The economic direction of a ledger entry."""

    EARN = "earn", "Earn"
    SPEND = "spend", "Spend"
    ADJUSTMENT = "adjustment", "Staff adjustment"


class RewardReason(models.TextChoices):
    """Why a balance changed. Stable codes  the ledger stores these."""

    LESSON_COMPLETED = "lesson_completed", "Lesson completed"
    COURSE_COMPLETED = "course_completed", "Course completed"
    QUIZ_COMPLETED = "quiz_completed", "Quiz completed"
    CERTIFICATE_ISSUED = "certificate_issued", "Certificate issued"
    ACHIEVEMENT_EARNED = "achievement_earned", "Achievement earned"
    REWARD_SPENT = "reward_spent", "Rewards spent"
    STAFF_ADJUSTMENT = "staff_adjustment", "Staff adjustment"


@dataclass(frozen=True)
class ReasonText:
    """Bilingual presentation of one reason code."""

    th: str
    en: str


# Presentation for every reason the ledger can carry. A registry test
# asserts completeness, so a new reason cannot ship without Thai text.
REASON_TEXT: dict[str, ReasonText] = {
    RewardReason.LESSON_COMPLETED: ReasonText(
        th="เรียนจบบทเรียน", en="Lesson completed"
    ),
    RewardReason.COURSE_COMPLETED: ReasonText(
        th="เรียนจบคอร์ส", en="Course completed"
    ),
    RewardReason.QUIZ_COMPLETED: ReasonText(
        th="ทำแบบทดสอบสำเร็จ", en="Quiz completed"
    ),
    RewardReason.CERTIFICATE_ISSUED: ReasonText(
        th="ได้รับใบประกาศนียบัตร", en="Certificate issued"
    ),
    RewardReason.ACHIEVEMENT_EARNED: ReasonText(
        th="ปลดล็อกความสำเร็จ", en="Achievement earned"
    ),
    RewardReason.REWARD_SPENT: ReasonText(
        th="ใช้คะแนนรางวัล", en="Rewards spent"
    ),
    RewardReason.STAFF_ADJUSTMENT: ReasonText(
        th="ปรับปรุงโดยทีมงาน", en="Adjusted by staff"
    ),
}

# The earning rules: reason → points. Only reasons here are claimable;
# spend/adjustment amounts come from the caller, never from a rule.
REWARD_RULES: dict[str, int] = {
    RewardReason.LESSON_COMPLETED: 5,
    RewardReason.COURSE_COMPLETED: 50,
    RewardReason.QUIZ_COMPLETED: 10,
    RewardReason.CERTIFICATE_ISSUED: 15,
    RewardReason.ACHIEVEMENT_EARNED: 10,
}

# `recipe_created` is deliberately NOT a source: publishing has no
# quality gate, so it would be a spam mint (ADR 0019 §13 future work).

EVENT_KEY_MAX_LENGTH = 100
NOTE_MAX_LENGTH = 255
# Guardrail on a single staff adjustment, not a business rule  one typo'd
# zero should not mint a fortune.
MAX_ADJUSTMENT_MAGNITUDE = 100_000


def event_key(reason: str, entity_id: object) -> str:
    """Build the stable idempotency key for one identified source fact.

    Args:
        reason: A :class:`RewardReason` value.
        entity_id: The owning domain's identity for the fact (lesson id,
            course id, quiz id, achievement type…).

    Returns:
        The key the unique constraint enforces per account.
    """
    return f"{reason}:{entity_id}"
