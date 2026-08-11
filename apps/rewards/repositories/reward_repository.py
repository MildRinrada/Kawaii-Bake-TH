"""The single write path of the reward economy.

A repository is justified here for the same reason as certificates
(ADR 0014): the write is genuinely intricate  one atomic unit that must
survive concurrent duplicates and concurrent spends  and it must exist
in exactly one place.

Concurrency is enforced by the database, never by Python:

- **Duplicate delivery** of one source event: both requests race to
  insert the same ``(account, event_key)`` row; the unique constraint
  admits one, the loser's savepoint rolls back (its balance update
  included) and the existing row is returned. `if exists` alone would
  pass both racers  the constraint cannot.
- **Concurrent spends**: the balance change is a conditional UPDATE
  (``WHERE balance >= amount``)  check and debit are one statement, and
  the row lock it takes holds until commit, serialising rivals. Zero
  rows updated means insufficient funds, atomically.
- A failure anywhere inside rolls back everything: no ledger row without
  its balance change, and vice versa.
"""

from __future__ import annotations

from django.db import IntegrityError, transaction
from django.db.models import F

from apps.rewards.models import RewardAccount, RewardTransaction


def get_or_create_account(*, user_id: int) -> RewardAccount:
    """Fetch the user's account, creating the zero row on first touch.

    Args:
        user_id: Primary key of the user.

    Returns:
        The account.
    """
    account, _created = RewardAccount.objects.get_or_create(user_id=user_id)
    return account


def apply_transaction(
    *,
    user_id: int,
    kind: str,
    reason_code: str,
    amount: int,
    event_key: str,
    note: str = "",
    actor_handle: str = "",
) -> tuple[RewardTransaction, bool]:
    """Atomically apply one economic change and append its ledger row.

    Args:
        user_id: Primary key of the account owner.
        kind: A :class:`RewardKind` value.
        reason_code: A :class:`RewardReason` value.
        amount: Signed, non-zero: positive credits, negative debits.
        event_key: The idempotency key; one grant per key per account.
        note: Optional human note (spend description, staff reason).
        actor_handle: Public handle of the acting staff member, for
            adjustments only.

    Returns:
        ``(transaction, created)``  ``created`` is ``False`` when the
        event key had already been processed, in which case the existing
        row is returned unchanged and no balance moved.

    Raises:
        InsufficientBalanceError: If a debit exceeds the balance  the
            conditional UPDATE updated zero rows.
    """
    from apps.rewards.exceptions import InsufficientBalanceError

    account = get_or_create_account(user_id=user_id)
    with transaction.atomic():
        try:
            with transaction.atomic():  # savepoint: duplicate loser rolls back
                if amount < 0:
                    updated = RewardAccount.objects.filter(
                        pk=account.pk, balance__gte=-amount
                    ).update(
                        balance=F("balance") + amount,
                        lifetime_spent=F("lifetime_spent") - amount,
                    )
                    if not updated:
                        raise InsufficientBalanceError
                else:
                    RewardAccount.objects.filter(pk=account.pk).update(
                        balance=F("balance") + amount,
                        lifetime_earned=F("lifetime_earned") + amount,
                    )
                account.refresh_from_db()
                row = RewardTransaction.objects.create(
                    account=account,
                    kind=kind,
                    amount=amount,
                    balance_after=account.balance,
                    reason_code=reason_code,
                    event_key=event_key,
                    note=note,
                    actor_handle=actor_handle,
                )
                return row, True
        except IntegrityError:
            existing = RewardTransaction.objects.get(
                account_id=account.pk, event_key=event_key
            )
            return existing, False
