"""Domain exceptions for the rewards app."""

from __future__ import annotations

from apps.core.exceptions import DomainError


class InsufficientBalanceError(DomainError):
    """Raised when a spend or downward adjustment exceeds the balance.

    409, the state-conflict family: the request was well-formed, the
    account state refuses it. The balance can never go negative — the
    conditional UPDATE that raises this is the enforcement, not a check
    that races ahead of it.
    """

    code = "insufficient_balance"
    status_code = 409
    message = "Not enough reward points."


class InvalidRewardAmountError(DomainError):
    """Raised when an amount is zero, negative (for spend), or absurd."""

    code = "invalid_amount"
    status_code = 400
    message = "Invalid reward amount."


class AdjustmentReasonRequiredError(DomainError):
    """Raised when a staff adjustment arrives without a reason."""

    code = "reason_required"
    status_code = 400
    message = "An adjustment requires a reason."


class RewardUserNotFoundError(DomainError):
    """Raised when a staff adjustment targets an unknown user."""

    code = "not_found"
    status_code = 404
    message = "User not found."
