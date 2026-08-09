"""The reconcile command: conservative, monotonic, dry-run first."""

from __future__ import annotations

from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps.courses.tests.factories import create_published_course, enroll_user
from apps.lessons.tests.factories import create_lesson
from apps.progress.tests.factories import complete_lesson_row
from apps.rewards.models import RewardAccount, RewardTransaction
from apps.rewards.services import reward_service
from apps.users.tests.factories import create_user


def reconcile(*args: str) -> str:
    out = StringIO()
    call_command("reconcile_rewards", *args, stdout=out)
    return out.getvalue()


class ReconcileTests(TestCase):
    """Repairs append and recompute; they never delete or subtract facts."""

    def setUp(self) -> None:
        self.instructor = create_user(username="rcteach")
        self.student = create_user(username="rclearn")
        course = create_published_course(instructor=self.instructor)
        lesson = create_lesson(course=course)
        enroll_user(user=self.student, course=course)
        complete_lesson_row(user=self.student, lesson=lesson)

    def test_dry_run_reports_but_writes_nothing(self) -> None:
        output = reconcile("--user", "rclearn")
        self.assertIn("DRY RUN", output)
        self.assertIn("missing earning: lesson_completed:", output)
        self.assertEqual(RewardTransaction.objects.count(), 0)
        self.assertFalse(RewardAccount.objects.exists())

    def test_apply_repairs_missing_earnings_once(self) -> None:
        reconcile("--user", "rclearn", "--apply")
        self.assertEqual(RewardTransaction.objects.count(), 1)
        balance = RewardAccount.objects.get(pk=self.student.id).balance
        self.assertEqual(balance, 5)

        # Running again repairs nothing further.
        output = reconcile("--user", "rclearn", "--apply")
        self.assertIn("0 missing earning(s)", output)
        self.assertEqual(RewardTransaction.objects.count(), 1)

    def test_drifted_account_is_recomputed_from_ledger(self) -> None:
        reconcile("--user", "rclearn", "--apply")
        # Simulate corruption of the materialized aggregate.
        RewardAccount.objects.filter(pk=self.student.id).update(balance=999)

        output = reconcile("--user", "rclearn")
        self.assertIn("account/ledger drift", output)
        self.assertEqual(
            RewardAccount.objects.get(pk=self.student.id).balance, 999
        )  # dry run touched nothing

        reconcile("--user", "rclearn", "--apply")
        self.assertEqual(RewardAccount.objects.get(pk=self.student.id).balance, 5)

    def test_repair_is_not_destructive(self) -> None:
        reconcile("--user", "rclearn", "--apply")
        reward_service.spend(user_id=self.student.id, amount=2, note="ใช้ไป")

        reconcile("--user", "rclearn", "--apply")
        # The spend survives; nothing was deleted or clawed back.
        self.assertEqual(RewardTransaction.objects.count(), 2)
        account = RewardAccount.objects.get(pk=self.student.id)
        self.assertEqual(account.balance, 3)
        self.assertEqual(account.lifetime_spent, 2)
