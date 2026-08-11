"""Domain exceptions for the notifications app."""

from __future__ import annotations

from apps.core.exceptions import DomainError


class NotificationNotFoundError(DomainError):
    """Raised when a notification is absent or not the caller's.

    "Not yours" and "does not exist" are the same 404  ownership is
    enforced by the selector, so no endpoint can address another user's
    notification.
    """

    code = "not_found"
    status_code = 404
    message = "Notification not found."


class CampaignNotFoundError(DomainError):
    """Raised when a campaign id matches nothing."""

    code = "not_found"
    status_code = 404
    message = "Campaign not found."


class TemplateNotFoundError(DomainError):
    """Raised when a template id matches nothing."""

    code = "not_found"
    status_code = 404
    message = "Template not found."


class CampaignStateError(DomainError):
    """Raised when an action does not fit the campaign's lifecycle state.

    Editing or deleting a sent campaign, canceling a draft, sending twice
    - sent rows are immutable evidence (ADR 0030), so these are 409s,
    not silent no-ops.
    """

    code = "campaign_state"
    status_code = 409
    message = "This action is not available in the campaign's current state."


class ScheduleInvalidError(DomainError):
    """Raised when a schedule request is malformed - a missing or
    non-future ``scheduled_at``."""

    code = "invalid_schedule"
    status_code = 400
    message = "The schedule is invalid."


class InvalidAudienceError(DomainError):
    """Raised when an audience document fails validation.

    Unknown kinds, missing or out-of-range params, unknown course slugs
    and unknown usernames all land here - the message says which.
    """

    code = "invalid_audience"
    status_code = 400
    message = "The audience configuration is invalid."


class UnresolvableVariablesError(DomainError):
    """Raised at send/schedule time when content embeds variables the
    chosen audience cannot resolve.

    ``{{user_name}}`` works everywhere; ``{{course_name}}`` only for
    course-scoped audiences; anything else never resolves. Drafts may
    hold anything - delivery may not lie.
    """

    code = "unresolvable_variables"
    status_code = 400
    message = "The content uses variables this audience cannot resolve."
