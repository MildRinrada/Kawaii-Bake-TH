"""Read-side queries for rewards."""

from __future__ import annotations

from dataclasses import dataclass

from django.db.models import Count, Q, QuerySet, Sum

from apps.rewards.models import RewardAccount, RewardTransaction


def get_account(*, user_id: int) -> RewardAccount | None:
    """Fetch the user's account without creating one.

    Read paths never write: a user who has earned nothing gets zeros
    serialized from nothing, not a row minted by a GET.

    Args:
        user_id: Primary key of the user.

    Returns:
        The account, or ``None``.
    """
    return RewardAccount.objects.filter(pk=user_id).first()


def list_transactions(*, user_id: int) -> QuerySet[RewardTransaction]:
    """The user's ledger, newest first.

    The account's primary key **is** the user id (PK-as-FK), so owner
    scoping is a direct column filter — no join, and another user's rows
    are unreachable by construction.

    Args:
        user_id: Primary key of the user.

    Returns:
        A lazy queryset for pagination, deterministically ordered.
    """
    return RewardTransaction.objects.filter(account_id=user_id).order_by(
        "-created_at", "-id"
    )


def existing_event_keys(*, user_id: int) -> set[str]:
    """Every event key already recorded for the user, in one query.

    Args:
        user_id: Primary key of the user.

    Returns:
        The recorded keys.
    """
    return set(
        RewardTransaction.objects.filter(account_id=user_id).values_list(
            "event_key", flat=True
        )
    )


@dataclass(frozen=True)
class LedgerTotals:
    """The ledger-derived truth an account row must agree with."""

    balance: int
    earned: int
    spent: int
    entries: int


def ledger_totals(*, user_id: int) -> LedgerTotals:
    """Recompute the account aggregates from the ledger, in one query.

    The reconciliation source of truth: the materialized account row is
    correct exactly when it equals this.

    Args:
        user_id: Primary key of the user.

    Returns:
        The totals (all zero for an empty ledger).
    """
    row = RewardTransaction.objects.filter(account_id=user_id).aggregate(
        earned=Sum("amount", filter=Q(amount__gt=0)),
        spent=Sum("amount", filter=Q(amount__lt=0)),
        entries=Count("id"),
    )
    earned = row["earned"] or 0
    spent = -(row["spent"] or 0)
    return LedgerTotals(
        balance=earned - spent, earned=earned, spent=spent, entries=row["entries"]
    )
