"""The economy core: accounts, earning, spending, adjusting, idempotency."""

from __future__ import annotations

from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.rewards.constants import RewardKind, RewardReason, event_key
from apps.rewards.exceptions import (
    AdjustmentReasonRequiredError,
    InsufficientBalanceError,
    InvalidRewardAmountError,
    RewardUserNotFoundError,
)
from apps.rewards.models import RewardAccount, RewardTransaction
from apps.rewards.repositories import reward_repository
from apps.rewards.selectors import reward_selector
from apps.rewards.services import reward_service
from apps.users.tests.factories import create_user


class AccountTests(TestCase):
    """Account lifecycle and the materialized aggregates."""

    def setUp(self) -> None:
        self.user = create_user(username="rwacct")

    def test_summary_is_zero_before_first_earn_and_creates_nothing(self) -> None:
        summary = reward_service.get_summary(user_id=self.user.id)
        self.assertEqual(
            (summary.balance, summary.lifetime_earned, summary.lifetime_spent),
            (0, 0, 0),
        )
        self.assertFalse(RewardAccount.objects.filter(pk=self.user.id).exists())

    def test_lifetime_totals_track_both_directions(self) -> None:
        reward_repository.apply_transaction(
            user_id=self.user.id,
            kind=RewardKind.EARN,
            reason_code=RewardReason.LESSON_COMPLETED,
            amount=50,
            event_key="lesson_completed:1",
        )
        reward_service.spend(user_id=self.user.id, amount=20)
        summary = reward_service.get_summary(user_id=self.user.id)
        self.assertEqual(summary.balance, 30)
        self.assertEqual(summary.lifetime_earned, 50)
        self.assertEqual(summary.lifetime_spent, 20)

    def test_summary_query_count(self) -> None:
        reward_repository.get_or_create_account(user_id=self.user.id)
        with self.assertNumQueries(1):
            reward_service.get_summary(user_id=self.user.id)


class EarnTests(TestCase):
    """Earning is atomic, snapshotted and idempotent per event."""

    def setUp(self) -> None:
        self.user = create_user(username="rwearn")

    def earn(self, key: str = "lesson_completed:1", amount: int = 5):
        return reward_repository.apply_transaction(
            user_id=self.user.id,
            kind=RewardKind.EARN,
            reason_code=RewardReason.LESSON_COMPLETED,
            amount=amount,
            event_key=key,
        )

    def test_successful_earn_writes_ledger_and_balance_together(self) -> None:
        row, created = self.earn()
        self.assertTrue(created)
        self.assertEqual(row.amount, 5)
        self.assertEqual(row.balance_after, 5)
        account = RewardAccount.objects.get(pk=self.user.id)
        self.assertEqual(account.balance, 5)
        self.assertEqual(account.lifetime_earned, 5)

    def test_balance_after_snapshots_the_running_balance(self) -> None:
        self.earn("lesson_completed:1")
        row, _ = self.earn("lesson_completed:2")
        self.assertEqual(row.balance_after, 10)

    def test_duplicate_event_returns_existing_and_moves_nothing(self) -> None:
        first, created_first = self.earn()
        second, created_second = self.earn()
        self.assertTrue(created_first)
        self.assertFalse(created_second)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(RewardTransaction.objects.count(), 1)
        self.assertEqual(RewardAccount.objects.get(pk=self.user.id).balance, 5)

    def test_unique_constraint_is_the_database_not_a_check(self) -> None:
        # The mechanism that survives concurrency: two inserts with one
        # event key cannot both commit, regardless of what Python checked.
        account = reward_repository.get_or_create_account(user_id=self.user.id)
        RewardTransaction.objects.create(
            account=account,
            kind=RewardKind.EARN,
            amount=5,
            balance_after=5,
            reason_code=RewardReason.LESSON_COMPLETED,
            event_key="k",
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            RewardTransaction.objects.create(
                account=account,
                kind=RewardKind.EARN,
                amount=5,
                balance_after=10,
                reason_code=RewardReason.LESSON_COMPLETED,
                event_key="k",
            )

    def test_race_loser_rolls_back_its_balance_update(self) -> None:
        # Simulate the exact interleaving a concurrent duplicate produces:
        # the row exists (the rival won) but our caller proceeds anyway.
        # The savepoint must discard our balance update and hand back the
        # winner's row — total effect of the race: one grant.
        account = reward_repository.get_or_create_account(user_id=self.user.id)
        RewardTransaction.objects.create(
            account=account,
            kind=RewardKind.EARN,
            amount=5,
            balance_after=5,
            reason_code=RewardReason.LESSON_COMPLETED,
            event_key="raced",
        )
        RewardAccount.objects.filter(pk=account.pk).update(
            balance=5, lifetime_earned=5
        )

        row, created = self.earn("raced")
        self.assertFalse(created)
        self.assertEqual(row.event_key, "raced")
        self.assertEqual(RewardAccount.objects.get(pk=account.pk).balance, 5)
        self.assertEqual(RewardTransaction.objects.count(), 1)

    def test_zero_amount_is_rejected_by_the_database(self) -> None:
        account = reward_repository.get_or_create_account(user_id=self.user.id)
        with self.assertRaises(IntegrityError), transaction.atomic():
            RewardTransaction.objects.create(
                account=account,
                kind=RewardKind.EARN,
                amount=0,
                balance_after=0,
                reason_code=RewardReason.LESSON_COMPLETED,
                event_key="zero",
            )


class SpendTests(TestCase):
    """Spending is guarded by the database, not by a racing read."""

    def setUp(self) -> None:
        self.user = create_user(username="rwspend")
        reward_repository.apply_transaction(
            user_id=self.user.id,
            kind=RewardKind.EARN,
            reason_code=RewardReason.COURSE_COMPLETED,
            amount=50,
            event_key="course_completed:1",
        )

    def test_successful_spend(self) -> None:
        row = reward_service.spend(user_id=self.user.id, amount=20, note="ทดลองใช้")
        self.assertEqual(row.amount, -20)
        self.assertEqual(row.balance_after, 30)
        self.assertEqual(row.kind, RewardKind.SPEND)
        self.assertEqual(RewardAccount.objects.get(pk=self.user.id).balance, 30)

    def test_insufficient_balance_leaves_state_untouched(self) -> None:
        with self.assertRaises(InsufficientBalanceError):
            reward_service.spend(user_id=self.user.id, amount=51)
        self.assertEqual(RewardAccount.objects.get(pk=self.user.id).balance, 50)
        self.assertEqual(RewardTransaction.objects.count(), 1)

    def test_balance_never_goes_negative_even_with_stale_reads(self) -> None:
        # Two rivals both read balance=50 and both try to spend 30. The
        # conditional UPDATE makes check-and-debit one statement, so the
        # second debit fails no matter what its Python side believed.
        stale_balance = RewardAccount.objects.get(pk=self.user.id).balance
        self.assertEqual(stale_balance, 50)
        reward_service.spend(user_id=self.user.id, amount=30)
        with self.assertRaises(InsufficientBalanceError):
            reward_service.spend(user_id=self.user.id, amount=30)
        self.assertEqual(RewardAccount.objects.get(pk=self.user.id).balance, 20)

    def test_spend_idempotency_key_makes_retries_safe(self) -> None:
        first = reward_service.spend(
            user_id=self.user.id, amount=10, idempotency_key="order-1"
        )
        second = reward_service.spend(
            user_id=self.user.id, amount=10, idempotency_key="order-1"
        )
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(RewardAccount.objects.get(pk=self.user.id).balance, 40)

    def test_invalid_amounts_rejected(self) -> None:
        for amount in (0, -5):
            with self.assertRaises(InvalidRewardAmountError):
                reward_service.spend(user_id=self.user.id, amount=amount)


class AdjustmentTests(TestCase):
    """Staff corrections are ledger entries — audited, guarded, idempotent."""

    def setUp(self) -> None:
        self.user = create_user(username="rwtarget")
        self.staff = create_user(username="rwstaff", is_staff=True)

    def adjust(self, **kwargs):
        defaults = {
            "target_username": "rwtarget",
            "amount": 25,
            "reason": "ชดเชยคะแนนจากเหตุขัดข้อง",
            "actor_handle": self.staff.username,
        }
        defaults.update(kwargs)
        return reward_service.adjust(**defaults)

    def test_adjustment_creates_audited_ledger_entry(self) -> None:
        row = self.adjust()
        self.assertEqual(row.kind, RewardKind.ADJUSTMENT)
        self.assertEqual(row.note, "ชดเชยคะแนนจากเหตุขัดข้อง")
        self.assertEqual(row.actor_handle, "rwstaff")
        self.assertEqual(RewardAccount.objects.get(pk=self.user.id).balance, 25)

    def test_reason_is_required(self) -> None:
        with self.assertRaises(AdjustmentReasonRequiredError):
            self.adjust(reason="   ")

    def test_unknown_user_is_a_404(self) -> None:
        with self.assertRaises(RewardUserNotFoundError):
            self.adjust(target_username="nobody-here")

    def test_downward_adjustment_cannot_overdraw(self) -> None:
        self.adjust(amount=10)
        with self.assertRaises(InsufficientBalanceError):
            self.adjust(amount=-11)
        self.assertEqual(RewardAccount.objects.get(pk=self.user.id).balance, 10)

    def test_adjustment_idempotency_key(self) -> None:
        first = self.adjust(idempotency_key="ticket-77")
        second = self.adjust(idempotency_key="ticket-77")
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(RewardAccount.objects.get(pk=self.user.id).balance, 25)

    def test_zero_and_absurd_amounts_rejected(self) -> None:
        for amount in (0, 10_000_000):
            with self.assertRaises(InvalidRewardAmountError):
                self.adjust(amount=amount)


class LedgerTotalsTests(TestCase):
    """The reconciliation truth: ledger aggregates in one query."""

    def test_totals_agree_with_account(self) -> None:
        user = create_user(username="rwtotals")
        reward_repository.apply_transaction(
            user_id=user.id,
            kind=RewardKind.EARN,
            reason_code=RewardReason.QUIZ_COMPLETED,
            amount=10,
            event_key=event_key(RewardReason.QUIZ_COMPLETED, 1),
        )
        reward_service.spend(user_id=user.id, amount=4)
        totals = reward_selector.ledger_totals(user_id=user.id)
        self.assertEqual((totals.balance, totals.earned, totals.spent), (6, 10, 4))
        account = RewardAccount.objects.get(pk=user.id)
        self.assertEqual(account.balance, totals.balance)
        self.assertEqual(account.lifetime_earned, totals.earned)
        self.assertEqual(account.lifetime_spent, totals.spent)
