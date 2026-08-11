"""Enumerations and magic values for the notifications app."""

from __future__ import annotations

from django.db import models


class NotificationEventType(models.TextChoices):
    """What happened. Exactly the wired events  new types are an
    ADR/docs change, not just another ``notify`` call (ADR 0016).
    Phase 10 shipped the first three; Phase 11 added the two Q&A events
    (ADR 0017)."""

    REVIEW_RECEIVED = "review_received", "Review received"
    COURSE_ENROLLMENT = "course_enrollment", "New course enrollment"
    ACHIEVEMENT_EARNED = "achievement_earned", "Achievement earned"
    QA_ANSWER_RECEIVED = "qa_answer_received", "Your question got an answer"
    QA_ANSWER_ACCEPTED = "qa_answer_accepted", "Your answer was accepted"
    # ADR 0028: the one staff-produced type. Broadcasts respect the same
    # per-event opt-out as every other type.
    ANNOUNCEMENT = "announcement", "Platform announcement"


class CampaignStatus(models.TextChoices):
    """Lifecycle of a staff campaign (ADR 0030).

    ``draft`` and ``scheduled`` are editable; ``sent`` is immutable
    evidence; ``canceled`` is a scheduled send that was called off."""

    DRAFT = "draft", "Draft"
    SCHEDULED = "scheduled", "Scheduled"
    SENT = "sent", "Sent"
    CANCELED = "canceled", "Canceled"


class AudienceKind(models.TextChoices):
    """Who a campaign targets. A closed set - each value maps to one
    cross-app selector, so an audience can never be an arbitrary query
    (ADR 0030)."""

    ALL = "all", "Every active account"
    ACTIVE = "active", "Signed in recently"
    NEW_USERS = "new_users", "Joined recently"
    COURSE_ENROLLED = "course_enrolled", "Enrolled in a course"
    COURSE_COMPLETED = "course_completed", "Completed a course"
    RECIPE_CREATORS = "recipe_creators", "Published recipe authors"
    COMMUNITY_CREATORS = "community_creators", "Community post authors"
    SKILL_LEVEL = "skill_level", "Declared skill level"
    SPECIFIC_USERS = "specific_users", "Named accounts"


TITLE_MAX_LENGTH = 200
BODY_MAX_LENGTH = 500
ACTOR_HANDLE_MAX_LENGTH = 150
LINK_MAX_LENGTH = 300

# Campaign composer fields (ADR 0030).
ICON_MAX_LENGTH = 16
CTA_MAX_LENGTH = 60
KIND_MAX_LENGTH = 40
TEMPLATE_NAME_MAX_LENGTH = 100
AUDIENCE_DAYS_MIN = 1
AUDIENCE_DAYS_MAX = 365
AUDIENCE_DAYS_DEFAULT = 30
AUDIENCE_USERNAMES_MAX = 100

# The variables campaigns may embed as ``{{name}}``. ``user_name`` is
# resolvable for every audience; ``course_name`` only when the audience
# is scoped to one course. Anything else is rejected at send time.
VARIABLE_USER_NAME = "user_name"
VARIABLE_COURSE_NAME = "course_name"
COURSE_SCOPED_AUDIENCES = frozenset(
    {AudienceKind.COURSE_ENROLLED, AudienceKind.COURSE_COMPLETED}
)
