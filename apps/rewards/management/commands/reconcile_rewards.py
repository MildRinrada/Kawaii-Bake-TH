"""Operational reconciliation of the reward economy.

Conservative and monotonic (ADR 0019 §10): it may append earnings whose
authoritative source fact exists but whose ledger entry is missing, and
it may recompute the materialized account aggregates from the ledger 
its own derived state. It never deletes a transaction, never subtracts a
suspected overpayment, and never invents a fact. Anything it cannot
repair safely, it reports.

Dry-run by default; ``--apply`` writes.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.rewards.models import RewardAccount
from apps.rewards.selectors import reward_selector
from apps.rewards.services import reward_service


class Command(BaseCommand):
    """``reconcile_rewards [--user HANDLE] [--apply]``"""

    help = (
        "Report (and with --apply, repair) missing reward earnings and "
        "account/ledger drift. Monotonic: appends and recomputes only."
    )

    def add_arguments(self, parser) -> None:
        """Register command options."""
        parser.add_argument(
            "--user", help="Restrict to one user by public handle."
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Write repairs. Without this flag the run is a dry run.",
        )

    def handle(self, *args, **options) -> None:
        """Run the reconciliation."""
        user_model = get_user_model()
        users = user_model.objects.filter(is_active=True).order_by("id")
        if options["user"]:
            users = users.filter(username__iexact=options["user"])
            if not users.exists():
                raise CommandError(f"unknown user: {options['user']}")

        apply_changes: bool = options["apply"]
        mode = "APPLY" if apply_changes else "DRY RUN"
        self.stdout.write(f"[{mode}] reconciling rewards…")

        total_missing = 0
        total_drift = 0
        for user in users.iterator():
            expected = reward_service._expected_events(user_id=user.id)
            recorded = reward_selector.existing_event_keys(user_id=user.id)
            missing = sorted(set(expected) - recorded)

            totals = reward_selector.ledger_totals(user_id=user.id)
            account = reward_selector.get_account(user_id=user.id)
            stored = (
                (account.balance, account.lifetime_earned, account.lifetime_spent)
                if account
                else (0, 0, 0)
            )
            derived = (totals.balance, totals.earned, totals.spent)
            drifted = stored != derived and (account or totals.entries)

            if not missing and not drifted:
                continue

            self.stdout.write(f"user {user.username}:")
            if missing:
                total_missing += len(missing)
                for key in missing:
                    self.stdout.write(f"  missing earning: {key}")
            if drifted:
                total_drift += 1
                self.stdout.write(
                    f"  account/ledger drift: stored={stored} ledger={derived}"
                )

            if not apply_changes:
                continue

            if missing:
                result = reward_service.claim(user_id=user.id)
                self.stdout.write(
                    f"  repaired: claimed {result['claimed']} "
                    f"(+{result['points']} points)"
                )
            if drifted:
                # Recompute the materialized aggregates from the ledger 
                # repair of this app's own derived state, never of facts.
                fresh = reward_selector.ledger_totals(user_id=user.id)
                RewardAccount.objects.update_or_create(
                    user_id=user.id,
                    defaults={
                        "balance": fresh.balance,
                        "lifetime_earned": fresh.earned,
                        "lifetime_spent": fresh.spent,
                    },
                )
                self.stdout.write("  account aggregates recomputed from ledger")

        self.stdout.write(
            f"[{mode}] done: {total_missing} missing earning(s), "
            f"{total_drift} drifted account(s)."
        )
        if not apply_changes and (total_missing or total_drift):
            self.stdout.write("Run again with --apply to repair.")
