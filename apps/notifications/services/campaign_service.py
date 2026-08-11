"""Business logic for staff notification campaigns (ADR 0030).

A campaign is composed (draft), optionally scheduled, and eventually
sent. Sending resolves the audience through the cross-app selectors,
drops announcement opt-outs, renders ``{{variables}}`` per recipient,
and bulk-creates the same per-recipient :class:`Notification` snapshots
machine events create - with a ``campaign`` backreference so read
receipts aggregate into honest analytics.

Sent campaigns are immutable evidence: no edit, no delete, no resend.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.courses.selectors import course_selector, enrollment_selector
from apps.gallery.selectors import gallery_selector
from apps.notifications.constants import (
    COURSE_SCOPED_AUDIENCES,
    VARIABLE_COURSE_NAME,
    VARIABLE_USER_NAME,
    AudienceKind,
    CampaignStatus,
    NotificationEventType,
)
from apps.notifications.exceptions import (
    CampaignNotFoundError,
    CampaignStateError,
    InvalidAudienceError,
    ScheduleInvalidError,
    TemplateNotFoundError,
    UnresolvableVariablesError,
)
from apps.notifications.models import (
    Notification,
    NotificationCampaign,
    NotificationPreference,
    NotificationTemplate,
)
from apps.notifications.validators import validate_audience
from apps.recipes.selectors import recipe_selector
from apps.users.selectors import user_selector

logger = logging.getLogger("kawaiibake.notifications")

VARIABLE_PATTERN = re.compile(r"\{\{\s*([a-z_]+)\s*\}\}")

# Which fields of a campaign may embed variables.
_TEMPLATED_FIELDS = ("title", "body")


def _embedded_variables(campaign: NotificationCampaign) -> set[str]:
    """Every ``{{variable}}`` name used in the campaign's content."""
    found: set[str] = set()
    for field in _TEMPLATED_FIELDS:
        found.update(VARIABLE_PATTERN.findall(getattr(campaign, field)))
    return found


def resolvable_variables(*, audience: dict[str, Any]) -> set[str]:
    """The variable names delivery can truthfully fill for this audience.

    Args:
        audience: A validated audience document.

    Returns:
        The resolvable names - ``user_name`` always, ``course_name``
        when the audience is scoped to one course.
    """
    names = {VARIABLE_USER_NAME}
    if audience.get("kind") in COURSE_SCOPED_AUDIENCES:
        names.add(VARIABLE_COURSE_NAME)
    return names


def _require_resolvable(campaign: NotificationCampaign) -> None:
    """Reject content whose variables this audience cannot fill."""
    unresolvable = _embedded_variables(campaign) - resolvable_variables(
        audience=campaign.audience
    )
    if unresolvable:
        raise UnresolvableVariablesError(
            "The content uses variables this audience cannot resolve: "
            + ", ".join(sorted(unresolvable))
            + "."
        )


def _course_ref_for(audience: dict[str, Any]):
    """Resolve the course a course-scoped audience points at, staff view."""
    ref = course_selector.get_course_ref(
        slug=audience["course_slug"], viewer_is_staff=True
    )
    if ref is None:
        raise InvalidAudienceError("Unknown course for this audience.")
    return ref


def resolve_audience_ids(*, audience: dict[str, Any]) -> list[int]:
    """Turn a validated audience document into active recipient ids.

    Every branch goes through a cross-app selector (ADR 0030) and every
    result is narrowed to active accounts - a deactivated account never
    receives a campaign.

    Args:
        audience: A validated audience document.

    Returns:
        The recipient ids, before opt-out filtering.

    Raises:
        InvalidAudienceError: When a referenced course or username does
            not exist.
    """
    kind = audience["kind"]
    if kind == AudienceKind.ALL:
        return user_selector.active_user_ids()
    if kind == AudienceKind.ACTIVE:
        return user_selector.recently_active_ids(days=audience["days"])
    if kind == AudienceKind.NEW_USERS:
        return user_selector.recently_joined_ids(days=audience["days"])
    if kind == AudienceKind.SKILL_LEVEL:
        return user_selector.ids_by_experience_level(level=audience["level"])
    if kind == AudienceKind.SPECIFIC_USERS:
        ids, missing = user_selector.match_usernames(
            usernames=audience["usernames"]
        )
        if missing:
            raise InvalidAudienceError(
                "Unknown usernames: " + ", ".join(missing) + "."
            )
        return ids
    if kind == AudienceKind.COURSE_ENROLLED:
        ref = _course_ref_for(audience)
        return user_selector.filter_active(
            user_ids=enrollment_selector.enrolled_user_ids(course_id=ref.id)
        )
    if kind == AudienceKind.COURSE_COMPLETED:
        ref = _course_ref_for(audience)
        return user_selector.filter_active(
            user_ids=enrollment_selector.completed_user_ids(course_id=ref.id)
        )
    if kind == AudienceKind.RECIPE_CREATORS:
        return user_selector.filter_active(
            user_ids=recipe_selector.published_author_ids()
        )
    # AudienceKind.COMMUNITY_CREATORS - the validator admits nothing else.
    return user_selector.filter_active(user_ids=gallery_selector.author_ids())


def _drop_opted_out(user_ids: list[int]) -> list[int]:
    """Remove accounts that opted out of the announcement event type."""
    opted_out = set(
        NotificationPreference.objects.filter(
            event_type=NotificationEventType.ANNOUNCEMENT, enabled=False
        ).values_list("user_id", flat=True)
    )
    return [user_id for user_id in user_ids if user_id not in opted_out]


def estimate_audience(*, audience: Any) -> int:
    """How many accounts a send with this audience would reach, today.

    The same pipeline delivery uses - resolve, then drop opt-outs - so
    the number the composer shows is the number a send would produce.

    Args:
        audience: The submitted audience document (validated here).

    Returns:
        The estimated recipient count.
    """
    normalized = validate_audience(audience)
    return len(_drop_opted_out(resolve_audience_ids(audience=normalized)))


# --------------------------------------------------------------------------
# Campaign lifecycle
# --------------------------------------------------------------------------


def _get_campaign(campaign_id: int) -> NotificationCampaign:
    campaign = NotificationCampaign.objects.filter(pk=campaign_id).first()
    if campaign is None:
        raise CampaignNotFoundError
    return campaign


_EDITABLE_STATUSES = (CampaignStatus.DRAFT, CampaignStatus.SCHEDULED)

# The writable composer fields, applied verbatim on create/update.
_CONTENT_FIELDS = ("kind", "icon", "title", "body", "cta_text", "link")


def _apply_schedule(
    campaign: NotificationCampaign, *, status: str, scheduled_at
) -> None:
    """Set the draft/scheduled pair, enforcing a future timestamp."""
    if status == CampaignStatus.SCHEDULED:
        if scheduled_at is None:
            raise ScheduleInvalidError(
                "A scheduled campaign needs 'scheduled_at'."
            )
        if scheduled_at <= timezone.now():
            raise ScheduleInvalidError("'scheduled_at' must be in the future.")
        _require_resolvable(campaign)
        campaign.status = CampaignStatus.SCHEDULED
        campaign.scheduled_at = scheduled_at
    else:
        campaign.status = CampaignStatus.DRAFT
        campaign.scheduled_at = None


def create_campaign(
    *,
    actor_id: int,
    audience: Any,
    status: str = CampaignStatus.DRAFT,
    scheduled_at=None,
    **content: str,
) -> NotificationCampaign:
    """Create a campaign as a draft or directly scheduled.

    Args:
        actor_id: The staff author.
        audience: The audience document (validated here).
        status: ``draft`` or ``scheduled``.
        scheduled_at: Required (and future) when scheduling.
        **content: The composer fields (:data:`_CONTENT_FIELDS`).

    Returns:
        The stored campaign.
    """
    campaign = NotificationCampaign(
        created_by_id=actor_id,
        audience=validate_audience(audience),
        **{field: content.get(field, "") for field in _CONTENT_FIELDS},
    )
    if not campaign.kind:
        campaign.kind = "custom"
    _apply_schedule(campaign, status=status, scheduled_at=scheduled_at)
    campaign.save()
    return campaign


def update_campaign(
    *,
    campaign_id: int,
    audience: Any = None,
    status: str | None = None,
    scheduled_at=None,
    **content: str,
) -> NotificationCampaign:
    """Update a draft or scheduled campaign.

    Args:
        campaign_id: Primary key of the campaign.
        audience: A replacement audience document, when provided.
        status: ``draft`` or ``scheduled``, when the mode changes.
        scheduled_at: The new send time, when scheduling.
        **content: Any composer fields to replace.

    Returns:
        The updated campaign.

    Raises:
        CampaignStateError: When the campaign is sent or canceled.
    """
    campaign = _get_campaign(campaign_id)
    if campaign.status not in _EDITABLE_STATUSES:
        raise CampaignStateError(
            "Sent and canceled campaigns cannot be edited - duplicate instead."
        )
    for field in _CONTENT_FIELDS:
        if field in content:
            setattr(campaign, field, content[field])
    if not campaign.kind:
        campaign.kind = "custom"
    if audience is not None:
        campaign.audience = validate_audience(audience)
    _apply_schedule(
        campaign,
        status=status or campaign.status,
        scheduled_at=(
            scheduled_at if scheduled_at is not None else campaign.scheduled_at
        ),
    )
    campaign.save()
    return campaign


def delete_campaign(*, campaign_id: int) -> None:
    """Delete a draft or canceled campaign.

    Sent campaigns are history and scheduled ones must be canceled
    first - both are 409s, not silent deletes.

    Args:
        campaign_id: Primary key of the campaign.
    """
    campaign = _get_campaign(campaign_id)
    if campaign.status not in (CampaignStatus.DRAFT, CampaignStatus.CANCELED):
        raise CampaignStateError(
            "Only draft and canceled campaigns can be deleted."
        )
    campaign.delete()


def cancel_campaign(*, campaign_id: int) -> NotificationCampaign:
    """Call off a scheduled send.

    Args:
        campaign_id: Primary key of the campaign.

    Returns:
        The (now canceled) campaign.
    """
    campaign = _get_campaign(campaign_id)
    if campaign.status != CampaignStatus.SCHEDULED:
        raise CampaignStateError("Only scheduled campaigns can be canceled.")
    campaign.status = CampaignStatus.CANCELED
    campaign.save(update_fields=["status", "updated_at"])
    return campaign


def _render(text: str, values: dict[str, str]) -> str:
    """Fill every ``{{variable}}`` from ``values`` (validated complete)."""
    return VARIABLE_PATTERN.sub(
        lambda match: values.get(match.group(1), match.group(0)), text
    )


def send_campaign(*, campaign_id: int, actor_id: int) -> int:
    """Deliver a draft or scheduled campaign now.

    Args:
        campaign_id: Primary key of the campaign.
        actor_id: The staff member pressing send.

    Returns:
        How many recipients the campaign was delivered to.

    Raises:
        CampaignStateError: When the campaign is already sent/canceled.
        UnresolvableVariablesError: When content variables cannot be
            filled for this audience.
        InvalidAudienceError: When the stored audience no longer
            resolves (course deleted, username gone).
    """
    with transaction.atomic():
        campaign = (
            NotificationCampaign.objects.select_for_update()
            .filter(pk=campaign_id)
            .first()
        )
        if campaign is None:
            raise CampaignNotFoundError
        if campaign.status not in _EDITABLE_STATUSES:
            raise CampaignStateError(
                "This campaign has already been sent or canceled."
            )
        audience = validate_audience(campaign.audience)
        _require_resolvable(campaign)

        shared: dict[str, str] = {}
        if audience["kind"] in COURSE_SCOPED_AUDIENCES:
            shared[VARIABLE_COURSE_NAME] = _course_ref_for(audience).title

        recipients = _drop_opted_out(resolve_audience_ids(audience=audience))
        names = user_selector.display_names(user_ids=recipients)
        Notification.objects.bulk_create(
            [
                Notification(
                    recipient_id=user_id,
                    event_type=NotificationEventType.ANNOUNCEMENT,
                    title=_render(
                        campaign.title,
                        {
                            **shared,
                            VARIABLE_USER_NAME: names.get(user_id, ""),
                        },
                    ),
                    body=_render(
                        campaign.body,
                        {
                            **shared,
                            VARIABLE_USER_NAME: names.get(user_id, ""),
                        },
                    ),
                    icon=campaign.icon,
                    cta_text=campaign.cta_text,
                    link=campaign.link,
                    campaign=campaign,
                )
                for user_id in recipients
            ],
            batch_size=500,
        )
        campaign.status = CampaignStatus.SENT
        campaign.sent_at = timezone.now()
        campaign.recipients_count = len(recipients)
        campaign.save(
            update_fields=[
                "status",
                "sent_at",
                "recipients_count",
                "updated_at",
            ]
        )
    logger.info(
        "campaign sent",
        extra={
            "campaign_id": campaign.pk,
            "actor_id": actor_id,
            "recipients": len(recipients),
        },
    )
    return len(recipients)


def dispatch_due_campaigns() -> int:
    """Send every scheduled campaign whose time has come.

    Called by the Celery beat task and the ``dispatch_campaigns``
    management command. Per-campaign failures are logged and skipped so
    one bad audience cannot block the queue.

    Returns:
        How many campaigns were sent.
    """
    due_ids = list(
        NotificationCampaign.objects.filter(
            status=CampaignStatus.SCHEDULED, scheduled_at__lte=timezone.now()
        ).values_list("id", flat=True)
    )
    sent = 0
    for campaign_id in due_ids:
        try:
            send_campaign(campaign_id=campaign_id, actor_id=0)
            sent += 1
        except Exception:  # noqa: BLE001 - the queue must keep moving
            logger.exception(
                "campaign dispatch failed", extra={"campaign_id": campaign_id}
            )
    return sent


# --------------------------------------------------------------------------
# Templates
# --------------------------------------------------------------------------


_TEMPLATE_FIELDS = ("name", "kind", "icon", "title", "body", "cta_text", "link")


def create_template(*, actor_id: int, **fields: str) -> NotificationTemplate:
    """Store a reusable composer template.

    Args:
        actor_id: The staff author.
        **fields: The template fields (:data:`_TEMPLATE_FIELDS`).

    Returns:
        The stored template.
    """
    template = NotificationTemplate(
        created_by_id=actor_id,
        **{field: fields.get(field, "") for field in _TEMPLATE_FIELDS},
    )
    if not template.kind:
        template.kind = "custom"
    template.save()
    return template


def update_template(
    *, template_id: int, is_archived: bool | None = None, **fields: str
) -> NotificationTemplate:
    """Update a template's fields or archived flag.

    Args:
        template_id: Primary key of the template.
        is_archived: The new archived state, when toggling.
        **fields: Any template fields to replace.

    Returns:
        The updated template.
    """
    template = NotificationTemplate.objects.filter(pk=template_id).first()
    if template is None:
        raise TemplateNotFoundError
    for field in _TEMPLATE_FIELDS:
        if field in fields:
            setattr(template, field, fields[field])
    if not template.kind:
        template.kind = "custom"
    if is_archived is not None:
        template.is_archived = is_archived
    template.save()
    return template


def delete_template(*, template_id: int) -> None:
    """Delete a template - configuration, not history, so this is allowed.

    Args:
        template_id: Primary key of the template.
    """
    deleted, _ = NotificationTemplate.objects.filter(pk=template_id).delete()
    if not deleted:
        raise TemplateNotFoundError
