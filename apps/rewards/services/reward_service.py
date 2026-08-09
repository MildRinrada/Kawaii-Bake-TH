"""Business logic of the reward economy: claim, spend, adjust.

Pull-based like the XP ledger (ADR 0015): no producer ever calls this
module. :func:`claim` reads **identified** facts through the owning
domains' public selectors and settles the ledger up to them — the same
boundary, upgraded from count arithmetic to per-event identity so that a
currency survives duplicate delivery (ADR 0019).
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

from apps.certificates.selectors import certificate_selector
from apps.progress.selectors import progress_selector
from apps.quizzes.selectors import attempt_selector
from apps.rewards.constants import (
    MAX_ADJUSTMENT_MAGNITUDE,
    REWARD_RULES,
    RewardKind,
    RewardReason,
    event_key,
)
from apps.rewards.exceptions import (
    AdjustmentReasonRequiredError,
    InvalidRewardAmountError,
    RewardUserNotFoundError,
)
from apps.rewards.models import RewardTransaction
from apps.rewards.repositories import reward_repository
from apps.rewards.selectors import reward_selector
from apps.users.selectors import user_selector

logger = logging.getLogger("kawaiibake.rewards")


@dataclass(frozen=True)
class RewardSummary:
    """The account figures the summary endpoint returns."""

    balance: int
    lifetime_earned: int
    lifetime_spent: int


def get_summary(*, user_id: int) -> RewardSummary:
    """The user's current balance and lifetime totals.

    Args:
        user_id: Primary key of the user.

    Returns:
        The summary — zeros when the user has never earned.
    """
    account = reward_selector.get_account(user_id=user_id)
    if account is None:
        return RewardSummary(balance=0, lifetime_earned=0, lifetime_spent=0)
    return RewardSummary(
        balance=account.balance,
        lifetime_earned=account.lifetime_earned,
        lifetime_spent=account.lifetime_spent,
    )


def _expected_events(*, user_id: int) -> dict[str, str]:
    """Every earnable event key for the user, mapped to its reason.

    One query per source domain, each through the owner's public
    identified-fact selector — rewards never re-derives "completed"
    itself.
    """
    expected: dict[str, str] = {}
    for lesson_id in progress_selector.completed_lesson_ids(user_id=user_id):
        expected[event_key(RewardReason.LESSON_COMPLETED, lesson_id)] = (
            RewardReason.LESSON_COMPLETED
        )
    for course_id in progress_selector.completed_course_ids(user_id=user_id):
        expected[event_key(RewardReason.COURSE_COMPLETED, course_id)] = (
            RewardReason.COURSE_COMPLETED
        )
    for quiz_id in attempt_selector.completed_quiz_ids(user_id=user_id):
        expected[event_key(RewardReason.QUIZ_COMPLETED, quiz_id)] = (
            RewardReason.QUIZ_COMPLETED
        )
    for course_id in certificate_selector.certified_course_ids(user_id=user_id):
        expected[event_key(RewardReason.CERTIFICATE_ISSUED, course_id)] = (
            RewardReason.CERTIFICATE_ISSUED
        )
    for achievement_type in sorted(
        certificate_selector.earned_types(user_id=user_id)
    ):
        expected[event_key(RewardReason.ACHIEVEMENT_EARNED, achievement_type)] = (
            RewardReason.ACHIEVEMENT_EARNED
        )
    return expected


def claim(*, user_id: int) -> dict[str, int]:
    """Settle the ledger up to the source domains' current facts.

    Idempotent and monotonic: each missing identified event earns exactly
    once (the unique event key absorbs races with a concurrent claim),
    already-settled events are skipped, and nothing is ever subtracted.
    Running twice claims nothing the second time.

    Args:
        user_id: Primary key of the user.

    Returns:
        ``{"claimed": n, "points": p, "balance": b}``.
    """
    expected = _expected_events(user_id=user_id)
    recorded = reward_selector.existing_event_keys(user_id=user_id)

    claimed = 0
    points = 0
    for key, reason in expected.items():
        if key in recorded:
            continue
        _row, created = reward_repository.apply_transaction(
            user_id=user_id,
            kind=RewardKind.EARN,
            reason_code=reason,
            amount=REWARD_RULES[reason],
            event_key=key,
        )
        if created:
            claimed += 1
            points += REWARD_RULES[reason]

    balance = get_summary(user_id=user_id).balance
    if claimed:
        logger.info(
            "rewards_claimed user=%s events=%s points=%s", user_id, claimed, points
        )
    return {"claimed": claimed, "points": points, "balance": balance}


def spend(
    *,
    user_id: int,
    amount: int,
    note: str = "",
    idempotency_key: str = "",
) -> RewardTransaction:
    """Debit the user's balance.

    The economy primitive only — what is being bought is a future
    phase's concern (ADR 0019 §11). A caller-supplied idempotency key
    makes retries safe; without one, each call is a distinct spend.

    Args:
        user_id: Primary key of the user.
        amount: Points to spend; must be positive.
        note: Optional description, Thai welcome.
        idempotency_key: Optional stable key for safe retries.

    Returns:
        The ledger row (the existing one on an idempotent replay).

    Raises:
        InvalidRewardAmountError: If ``amount`` is not a positive number.
        InsufficientBalanceError: If the balance cannot cover it.
    """
    if not isinstance(amount, int) or amount <= 0:
        raise InvalidRewardAmountError

    key = f"spend:{idempotency_key or uuid.uuid4().hex}"
    row, created = reward_repository.apply_transaction(
        user_id=user_id,
        kind=RewardKind.SPEND,
        reason_code=RewardReason.REWARD_SPENT,
        amount=-amount,
        event_key=key,
        note=note,
    )
    if created:
        logger.info("rewards_spent user=%s amount=%s", user_id, amount)
    return row


def adjust(
    *,
    target_username: str,
    amount: int,
    reason: str,
    actor_handle: str,
    idempotency_key: str = "",
) -> RewardTransaction:
    """Staff correction of a user's balance, as an auditable ledger entry.

    Never mutates the balance directly — the adjustment is a transaction
    like any other, with the staff member's public handle snapshotted and
    the reason required. A downward adjustment obeys the same
    insufficient-balance guard as a spend: the balance cannot go negative
    even by staff hand.

    Args:
        target_username: Public handle of the account owner.
        amount: Signed, non-zero, magnitude-capped.
        reason: Required free-text justification, Thai welcome.
        actor_handle: Public handle of the acting staff member.
        idempotency_key: Optional stable key for safe retries.

    Returns:
        The ledger row (the existing one on an idempotent replay).

    Raises:
        RewardUserNotFoundError: If no such user exists.
        InvalidRewardAmountError: If the amount is zero or absurd.
        AdjustmentReasonRequiredError: If the reason is blank.
        InsufficientBalanceError: If a debit exceeds the balance.
    """
    if not reason.strip():
        raise AdjustmentReasonRequiredError
    if (
        not isinstance(amount, int)
        or amount == 0
        or abs(amount) > MAX_ADJUSTMENT_MAGNITUDE
    ):
        raise InvalidRewardAmountError

    target = user_selector.get_by_username(username=target_username)
    if target is None:
        raise RewardUserNotFoundError

    key = f"adjustment:{idempotency_key or uuid.uuid4().hex}"
    row, created = reward_repository.apply_transaction(
        user_id=target.id,
        kind=RewardKind.ADJUSTMENT,
        reason_code=RewardReason.STAFF_ADJUSTMENT,
        amount=amount,
        event_key=key,
        note=reason.strip(),
        actor_handle=actor_handle,
    )
    if created:
        logger.info(
            "rewards_adjusted user=%s amount=%s by=%s",
            target.id,
            amount,
            actor_handle,
        )
    return row
