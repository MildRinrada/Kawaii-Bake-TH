"""Serializers for the security surface.

Two audiences with very different trust levels:

* **Public**  the client policy (read-only, no user data) and the signal
  ingest. Write shapes are :class:`StrictSerializer` and every field is
  bounded, because this is the one endpoint an unauthenticated attacker
  can post to on purpose.
* **Staff**  the dashboard's read models and its three actions.

No serializer here ever exposes a user's email; where an actor is shown
it is the public handle, matching the platform-wide rule.
"""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.common.api.serializers import StrictSerializer
from apps.security.constants import (
    CLIENT_REPORTABLE,
    EDGE_REPORTABLE,
    NOTE_MAX_LENGTH,
    PATH_MAX_LENGTH,
    USER_AGENT_MAX_LENGTH,
    ReviewState,
    SignalKind,
    ThreatLevel,
)

#: How many keys a client may attach to one reported signal.
MAX_DETAIL_KEYS = 8


class BoundedDetailField(serializers.DictField):
    """A small string-to-string map from an untrusted client.

    ``DictField`` bounds neither the number of keys nor their length, and
    this field is written straight into a ``JSONField`` by an endpoint
    anonymous callers can post to. Both bounds are enforced here so the
    limit lives next to the field rather than in a view.
    """

    def __init__(self, **kwargs: Any) -> None:
        """Constrain values to short strings."""
        kwargs.setdefault("child", serializers.CharField(max_length=120))
        super().__init__(**kwargs)

    def to_internal_value(self, data: Any) -> dict[str, str]:
        """Reject oversized maps before they reach the database.

        Raises:
            rest_framework.exceptions.ValidationError: On too many keys.
        """
        value = super().to_internal_value(data)
        if len(value) > MAX_DETAIL_KEYS:
            raise serializers.ValidationError(
                f"Provide at most {MAX_DETAIL_KEYS} keys."
            )
        return value


# --------------------------------------------------------------------------
# Public
# --------------------------------------------------------------------------


class ClientPolicySerializer(serializers.Serializer):
    """What the browser guard is allowed to do, as configured by env.

    Served to anyone, including anonymous visitors  it contains no user
    data and describes only this deployment's own posture. Publishing it
    is not a leak: the guard's behaviour is visible in the shipped
    JavaScript regardless, and a client that cannot read the policy would
    have to hard-code one, which is exactly the duplication this endpoint
    exists to prevent.
    """

    guard_mode = serializers.ChoiceField(choices=["off", "detect", "deter"])
    exempt_authenticated = serializers.BooleanField()
    report_signals = serializers.BooleanField()


class ClientSignalSerializer(StrictSerializer):
    """One browser-reported observation.

    ``kind`` is constrained to the client-reportable set at the schema
    level as well as in the service, so the published OpenAPI document
    tells the truth about what this endpoint accepts.

    There is deliberately **no ``ip`` field**. The address is taken from
    the connection; accepting one from the body would let any visitor
    attribute events to anyone.
    """

    kind = serializers.ChoiceField(choices=sorted(CLIENT_REPORTABLE))
    path = serializers.CharField(
        max_length=PATH_MAX_LENGTH,
        required=False,
        allow_blank=True,
        help_text="The frontend route the visitor was on.",
    )
    detail = BoundedDetailField(
        required=False,
        help_text="Bounded client context; string values only, few keys.",
    )


class EdgeSignalSerializer(StrictSerializer):
    """One signal forwarded by the trusted frontend edge.

    Unlike :class:`ClientSignalSerializer` this one **does** carry an
    ``ip``  the visitor's, as the edge saw it. That is only safe because
    the caller proves itself with the shared secret first; the field is
    the whole reason the secret exists.
    """

    kind = serializers.ChoiceField(choices=sorted(EDGE_REPORTABLE))
    ip = serializers.IPAddressField()
    path = serializers.CharField(
        max_length=PATH_MAX_LENGTH, required=False, allow_blank=True
    )
    user_agent = serializers.CharField(
        max_length=USER_AGENT_MAX_LENGTH, required=False, allow_blank=True
    )
    detail = BoundedDetailField(required=False)


class ClientSignalResultSerializer(serializers.Serializer):
    """The ingest endpoint's acknowledgement.

    Says only whether the signal was stored. It never reports the
    caller's score or level: telling a probe how close it is to being
    blocked turns the dashboard into a tuning aid for the attacker.
    """

    recorded = serializers.BooleanField()


# --------------------------------------------------------------------------
# Staff  reads
# --------------------------------------------------------------------------


class SecurityEventSerializer(serializers.Serializer):
    """One row of the event log."""

    id = serializers.IntegerField(read_only=True)
    kind = serializers.CharField(read_only=True)
    kind_label = serializers.SerializerMethodField()
    severity = serializers.CharField(read_only=True)
    score_delta = serializers.FloatField(read_only=True)
    ip = serializers.CharField(read_only=True)
    user_agent = serializers.CharField(read_only=True)
    path = serializers.CharField(read_only=True)
    method = serializers.CharField(read_only=True)
    status_code = serializers.IntegerField(read_only=True, allow_null=True)
    actor_handle = serializers.SerializerMethodField()
    request_id = serializers.CharField(read_only=True)
    detail = serializers.DictField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)

    def get_kind_label(self, obj: Any) -> str:
        """Return the human label for the signal kind."""
        return SignalKind(obj.kind).label

    def get_actor_handle(self, obj: Any) -> str:
        """Return the signed-in user's public handle, never their email."""
        return obj.actor.username if obj.actor else ""


class ThreatProfileSerializer(serializers.Serializer):
    """One offender row.

    ``score`` is the **stored** value; ``current_score`` is that value
    decayed to now. Both are exposed because they answer different
    questions  "how bad was it at its worst" and "how bad is it right
    now"  and a client that only saw one would have to guess the other.
    """

    id = serializers.IntegerField(read_only=True)
    ip = serializers.CharField(read_only=True)
    score = serializers.FloatField(read_only=True)
    current_score = serializers.SerializerMethodField()
    level = serializers.CharField(read_only=True)
    event_count = serializers.IntegerField(read_only=True)
    last_kind = serializers.CharField(read_only=True)
    last_kind_label = serializers.SerializerMethodField()
    last_path = serializers.CharField(read_only=True)
    last_user_agent = serializers.CharField(read_only=True)
    first_seen_at = serializers.DateTimeField(read_only=True)
    last_seen_at = serializers.DateTimeField(read_only=True)
    blocked_until = serializers.DateTimeField(read_only=True, allow_null=True)
    is_blocked = serializers.SerializerMethodField()
    review_state = serializers.CharField(read_only=True)
    reviewed_at = serializers.DateTimeField(read_only=True, allow_null=True)
    reviewed_by_handle = serializers.SerializerMethodField()
    note = serializers.CharField(read_only=True)

    def get_current_score(self, obj: Any) -> float:
        """Return the score decayed to this instant."""
        from apps.security.services import threat_service

        return round(threat_service.current_score(obj), 2)

    def get_last_kind_label(self, obj: Any) -> str:
        """Return the human label for the most recent signal kind."""
        return SignalKind(obj.last_kind).label if obj.last_kind else ""

    def get_is_blocked(self, obj: Any) -> bool:
        """Whether a block is in force right now."""
        from apps.security.services import threat_service

        return threat_service.is_blocked(obj)

    def get_reviewed_by_handle(self, obj: Any) -> str:
        """Return the reviewing staff member's public handle."""
        return obj.reviewed_by.username if obj.reviewed_by else ""


class ThreatProfileDetailSerializer(ThreatProfileSerializer):
    """An offender plus the evidence behind its score."""

    recent_events = SecurityEventSerializer(many=True, read_only=True)


class SecuritySummarySerializer(serializers.Serializer):
    """The dashboard's headline counters."""

    generated_at = serializers.DateTimeField()
    profiles_total = serializers.IntegerField()
    profiles_by_level = serializers.DictField(child=serializers.IntegerField())
    profiles_blocked = serializers.IntegerField()
    profiles_open = serializers.IntegerField()
    events_total = serializers.IntegerField()
    events_24h = serializers.IntegerField()
    events_7d = serializers.IntegerField()
    events_by_kind_7d = serializers.DictField(child=serializers.IntegerField())
    top_offenders = serializers.ListField(child=serializers.DictField())


class SecurityVocabularySerializer(serializers.Serializer):
    """The label vocabulary, so the dashboard never hard-codes it.

    Filters render from this. A signal kind added on the backend appears
    in the admin's filter list without a frontend deploy, which is the
    whole reason it is an endpoint rather than a constant in TypeScript.
    """

    kinds = serializers.ListField(child=serializers.DictField())
    levels = serializers.ListField(child=serializers.DictField())
    review_states = serializers.ListField(child=serializers.DictField())


# --------------------------------------------------------------------------
# Staff  actions
# --------------------------------------------------------------------------


class BlockRequestSerializer(StrictSerializer):
    """How long to block an address for."""

    minutes = serializers.IntegerField(min_value=1, max_value=60 * 24 * 30)


class ReviewRequestSerializer(StrictSerializer):
    """An operator's triage decision."""

    state = serializers.ChoiceField(
        choices=[ReviewState.ACKNOWLEDGED.value, ReviewState.IGNORED.value]
    )
    note = serializers.CharField(
        max_length=NOTE_MAX_LENGTH, required=False, allow_blank=True
    )


class PaginatedFilterSerializer(StrictSerializer):
    """Base for strict query-parameter validation on a paginated list.

    A strict serializer rejects any key it does not declare  which is
    the point, so a typo'd filter is a 400 rather than a silently
    unfiltered page. That makes it the serializer's job to know about the
    paginator's own parameters too: without these two fields, page 2 of
    any list would be rejected as an unknown filter.
    """

    page = serializers.IntegerField(min_value=1, required=False)
    page_size = serializers.IntegerField(min_value=1, max_value=200, required=False)


class EventFilterSerializer(PaginatedFilterSerializer):
    """Query parameters accepted by the event log."""

    kind = serializers.ChoiceField(
        choices=SignalKind.choices, required=False, allow_blank=True
    )
    severity = serializers.ChoiceField(
        choices=ThreatLevel.choices, required=False, allow_blank=True
    )
    ip = serializers.CharField(max_length=45, required=False, allow_blank=True)
    search = serializers.CharField(max_length=120, required=False, allow_blank=True)
    since_hours = serializers.IntegerField(
        min_value=1, max_value=24 * 90, required=False
    )


class ProfileFilterSerializer(PaginatedFilterSerializer):
    """Query parameters accepted by the offender list."""

    level = serializers.ChoiceField(
        choices=ThreatLevel.choices, required=False, allow_blank=True
    )
    review_state = serializers.ChoiceField(
        choices=ReviewState.choices, required=False, allow_blank=True
    )
    blocked = serializers.BooleanField(required=False, allow_null=True)
    search = serializers.CharField(max_length=120, required=False, allow_blank=True)
    ordering = serializers.ChoiceField(
        choices=["-score", "score", "-last_seen_at", "last_seen_at"],
        required=False,
        allow_blank=True,
    )
