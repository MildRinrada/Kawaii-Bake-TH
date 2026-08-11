"""Scoring, decay, banding and enforcement."""

from __future__ import annotations

from datetime import timedelta

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.security.constants import (
    SCORE_HALF_LIFE_HOURS,
    SIGNAL_WEIGHTS,
    ReviewState,
    SignalKind,
    ThreatLevel,
    level_for_score,
)
from apps.security.models import SecurityEvent, ThreatProfile
from apps.security.services import threat_service


class LevelBandingTests(TestCase):
    """The score-to-band mapping operators read off the dashboard."""

    def test_each_band_starts_at_its_documented_floor(self) -> None:
        self.assertEqual(level_for_score(0), ThreatLevel.LOW)
        self.assertEqual(level_for_score(14.9), ThreatLevel.LOW)
        self.assertEqual(level_for_score(15), ThreatLevel.MEDIUM)
        self.assertEqual(level_for_score(44.9), ThreatLevel.MEDIUM)
        self.assertEqual(level_for_score(45), ThreatLevel.HIGH)
        self.assertEqual(level_for_score(84.9), ThreatLevel.HIGH)
        self.assertEqual(level_for_score(85), ThreatLevel.CRITICAL)

    def test_one_honeypot_hit_alone_reaches_high(self) -> None:
        # The calibration claim in constants.py, asserted rather than hoped.
        self.assertEqual(
            level_for_score(SIGNAL_WEIGHTS[SignalKind.HONEYPOT_PATH]),
            ThreatLevel.HIGH,
        )

    def test_two_honeypot_hits_reach_critical(self) -> None:
        # The other half of the calibration claim: one probe is worth
        # investigating, two is worth stopping.
        self.assertEqual(
            level_for_score(SIGNAL_WEIGHTS[SignalKind.HONEYPOT_PATH] * 2),
            ThreatLevel.CRITICAL,
        )

    def test_a_single_context_menu_click_stays_low(self) -> None:
        self.assertEqual(
            level_for_score(SIGNAL_WEIGHTS[SignalKind.CONTEXT_MENU_ATTEMPT]),
            ThreatLevel.LOW,
        )


class DecayTests(TestCase):
    """Scores must age out without a cron job."""

    def test_a_score_halves_after_one_half_life(self) -> None:
        now = timezone.now()
        decayed = threat_service.decayed_score(
            score=80.0,
            since=now - timedelta(hours=SCORE_HALF_LIFE_HOURS),
            now=now,
        )
        self.assertAlmostEqual(decayed, 40.0, places=4)

    def test_a_fresh_score_does_not_decay(self) -> None:
        now = timezone.now()
        self.assertEqual(
            threat_service.decayed_score(score=50.0, since=now, now=now), 50.0
        )

    def test_recording_after_a_gap_scores_against_the_decayed_value(self) -> None:
        threat_service.record(kind=SignalKind.HONEYPOT_PATH, ip="203.0.113.9")
        profile = ThreatProfile.objects.get(ip="203.0.113.9")

        # Pretend the first hit was two half-lives ago.
        ThreatProfile.objects.filter(pk=profile.pk).update(
            last_seen_at=timezone.now() - timedelta(hours=SCORE_HALF_LIFE_HOURS * 2)
        )
        threat_service.record(kind=SignalKind.CONTEXT_MENU_ATTEMPT, ip="203.0.113.9")

        profile.refresh_from_db()
        # 45 decayed to a quarter (11.25) plus the new 1.
        self.assertAlmostEqual(profile.score, 12.25, places=2)
        self.assertEqual(profile.level, ThreatLevel.LOW)


class RecordTests(TestCase):
    """What one observation writes."""

    def test_recording_creates_the_event_and_the_profile_together(self) -> None:
        event = threat_service.record(
            kind=SignalKind.SCANNER_AGENT,
            ip="198.51.100.4",
            user_agent="sqlmap/1.7",
            path="/api/v1/recipes/",
            method="GET",
        )
        self.assertIsNotNone(event)
        profile = ThreatProfile.objects.get(ip="198.51.100.4")
        self.assertEqual(profile.event_count, 1)
        self.assertEqual(profile.score, SIGNAL_WEIGHTS[SignalKind.SCANNER_AGENT])
        self.assertEqual(profile.level, ThreatLevel.HIGH)
        self.assertEqual(profile.last_kind, SignalKind.SCANNER_AGENT)

    def test_event_severity_is_the_signals_own_weight_not_the_running_total(
        self,
    ) -> None:
        # Two honeypot hits push the profile to critical, but each event
        # stays "high"  history must not be rewritten by what came later.
        threat_service.record(kind=SignalKind.HONEYPOT_PATH, ip="198.51.100.5")
        threat_service.record(kind=SignalKind.HONEYPOT_PATH, ip="198.51.100.5")

        self.assertEqual(
            ThreatProfile.objects.get(ip="198.51.100.5").level, ThreatLevel.CRITICAL
        )
        severities = set(
            SecurityEvent.objects.filter(ip="198.51.100.5").values_list(
                "severity", flat=True
            )
        )
        self.assertEqual(severities, {ThreatLevel.HIGH})

    def test_attacker_controlled_text_is_truncated_to_the_column_width(self) -> None:
        event = threat_service.record(
            kind=SignalKind.HONEYPOT_PATH,
            ip="198.51.100.6",
            path="/" + ("a" * 5000),
            user_agent="b" * 5000,
        )
        self.assertEqual(len(event.path), 400)
        self.assertEqual(len(event.user_agent), 400)

    @override_settings(SECURITY_TRUSTED_IPS=["203.0.113.77"])
    def test_a_trusted_address_is_never_scored(self) -> None:
        self.assertIsNone(
            threat_service.record(kind=SignalKind.SCANNER_AGENT, ip="203.0.113.77")
        )
        self.assertFalse(ThreatProfile.objects.filter(ip="203.0.113.77").exists())

    @override_settings(SECURITY_WATCH_ENABLED=False)
    def test_the_master_switch_stops_all_recording(self) -> None:
        self.assertIsNone(
            threat_service.record(kind=SignalKind.SCANNER_AGENT, ip="203.0.113.78")
        )
        self.assertEqual(SecurityEvent.objects.count(), 0)

    def test_fresh_activity_reopens_a_dismissed_profile(self) -> None:
        threat_service.record(kind=SignalKind.HONEYPOT_PATH, ip="198.51.100.7")
        profile = ThreatProfile.objects.get(ip="198.51.100.7")
        ThreatProfile.objects.filter(pk=profile.pk).update(
            review_state=ReviewState.IGNORED
        )

        threat_service.record(kind=SignalKind.SQLI_PROBE, ip="198.51.100.7")

        profile.refresh_from_db()
        self.assertEqual(profile.review_state, ReviewState.OPEN)


class ClientSignalTests(TestCase):
    """The rule that makes the public ingest safe."""

    def test_a_client_may_report_only_client_reportable_kinds(self) -> None:
        event = threat_service.record_client_signal(
            kind=SignalKind.DEVTOOLS_OPENED, ip="198.51.100.8"
        )
        self.assertIsNotNone(event)

    def test_a_client_cannot_manufacture_a_server_only_signal(self) -> None:
        from apps.security.exceptions import SignalNotClientReportableError

        with self.assertRaises(SignalNotClientReportableError):
            threat_service.record_client_signal(
                kind=SignalKind.SCANNER_AGENT, ip="198.51.100.9"
            )
        self.assertFalse(SecurityEvent.objects.filter(ip="198.51.100.9").exists())

    def test_client_signals_alone_cannot_reach_a_blocking_band(self) -> None:
        # Ten devtools reports  the loudest a browser can be  must not
        # outrank a single real probe.
        for _ in range(10):
            threat_service.record_client_signal(
                kind=SignalKind.DEVTOOLS_OPENED, ip="198.51.100.10"
            )
        profile = ThreatProfile.objects.get(ip="198.51.100.10")
        self.assertNotEqual(profile.level, ThreatLevel.CRITICAL)


class AutoBlockTests(TestCase):
    """Automatic enforcement, which is off unless an operator asks for it."""

    def test_reaching_critical_does_not_block_by_default(self) -> None:
        for _ in range(3):
            threat_service.record(kind=SignalKind.SCANNER_AGENT, ip="198.51.100.11")
        profile = ThreatProfile.objects.get(ip="198.51.100.11")
        self.assertEqual(profile.level, ThreatLevel.CRITICAL)
        self.assertIsNone(profile.blocked_until)

    @override_settings(SECURITY_AUTO_BLOCK=True, SECURITY_AUTO_BLOCK_MINUTES=30)
    def test_auto_block_engages_only_when_enabled(self) -> None:
        for _ in range(3):
            threat_service.record(kind=SignalKind.SCANNER_AGENT, ip="198.51.100.12")
        profile = ThreatProfile.objects.get(ip="198.51.100.12")
        self.assertTrue(threat_service.is_blocked(profile))
        # Automatic, so no operator is recorded as responsible.
        self.assertIsNone(profile.blocked_by_id)


class BlockLifecycleTests(TestCase):
    """A block is always time-boxed and always attributable."""

    def setUp(self) -> None:
        from django.contrib.auth import get_user_model

        self.staff = get_user_model().objects.create_user(
            username="secops",
            email="secops@kawaiibake.local",
            password="Kawaii!Chef2026",
            is_staff=True,
        )
        threat_service.record(kind=SignalKind.HONEYPOT_PATH, ip="198.51.100.20")
        self.profile = ThreatProfile.objects.get(ip="198.51.100.20")

    def test_blocking_records_who_and_for_how_long(self) -> None:
        profile = threat_service.block(
            profile_id=self.profile.pk, minutes=15, actor_id=self.staff.id
        )
        self.assertTrue(threat_service.is_blocked(profile))
        self.assertEqual(profile.blocked_by_id, self.staff.id)

    def test_a_lapsed_block_reads_as_unblocked_with_no_sweep(self) -> None:
        threat_service.block(
            profile_id=self.profile.pk, minutes=15, actor_id=self.staff.id
        )
        ThreatProfile.objects.filter(pk=self.profile.pk).update(
            blocked_until=timezone.now() - timedelta(minutes=1)
        )
        self.profile.refresh_from_db()
        self.assertFalse(threat_service.is_blocked(self.profile))
        # The window survives as history rather than being nulled out.
        self.assertIsNotNone(self.profile.blocked_until)

    def test_review_changes_no_score_and_deletes_no_evidence(self) -> None:
        before = self.profile.score
        profile = threat_service.review(
            profile_id=self.profile.pk,
            state=ReviewState.IGNORED,
            actor_id=self.staff.id,
            note="office VPN",
        )
        self.assertEqual(profile.score, before)
        self.assertEqual(profile.review_state, ReviewState.IGNORED)
        self.assertEqual(SecurityEvent.objects.filter(ip="198.51.100.20").count(), 1)
