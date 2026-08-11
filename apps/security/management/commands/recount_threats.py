"""Rebuild every threat profile from the events underneath it.

The profile is a cached aggregate. This command is the proof that it is
only ever a cache: run it and the numbers must not move. It exists for
three moments  after re-tuning
:data:`~apps.security.constants.SIGNAL_WEIGHTS`, after restoring a
database, and whenever an operator suspects drift.

It never invents a profile for an address with no events, and it never
touches ``blocked_until`` or the review fields: those are operator
decisions, not derived values.
"""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.security.constants import SIGNAL_WEIGHTS, level_for_score
from apps.security.models import SecurityEvent, ThreatProfile
from apps.security.services.threat_service import decayed_score


class Command(BaseCommand):
    """Recompute ``score``, ``level`` and ``event_count`` from the event log."""

    help = "Rebuild threat profiles from their security events."

    def add_arguments(self, parser: Any) -> None:
        """Register the dry-run flag."""
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report drift without writing anything.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        """Replay each address's events in order and compare."""
        now = timezone.now()
        dry_run = bool(options["dry_run"])
        drifted = 0

        for profile in ThreatProfile.objects.all():
            events = list(
                SecurityEvent.objects.filter(ip=profile.ip).order_by("created_at")
            )
            score = 0.0
            previous = None
            for event in events:
                if previous is not None:
                    score = decayed_score(
                        score=score, since=previous, now=event.created_at
                    )
                score += float(SIGNAL_WEIGHTS.get(event.kind, event.score_delta))
                previous = event.created_at

            level = level_for_score(score)
            changed = (
                abs(score - profile.score) > 0.01
                or level != profile.level
                or len(events) != profile.event_count
            )
            if not changed:
                continue

            drifted += 1
            self.stdout.write(
                f"{profile.ip}: score {profile.score:.1f} -> {score:.1f}, "
                f"level {profile.level} -> {level}, "
                f"events {profile.event_count} -> {len(events)}"
            )
            if dry_run:
                continue
            profile.score = score
            profile.level = level
            profile.event_count = len(events)
            if previous is not None:
                profile.last_seen_at = previous
            profile.save(
                update_fields=["score", "level", "event_count", "last_seen_at"]
            )

        verb = "would fix" if dry_run else "fixed"
        self.stdout.write(
            self.style.SUCCESS(f"{verb} {drifted} drifted profile(s) as of {now:%F %T}")
        )
