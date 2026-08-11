"""The security HTTP surface: two public endpoints, seven staff ones."""

from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.security.constants import ReviewState, SignalKind, ThreatLevel
from apps.security.models import SecurityEvent, ThreatProfile
from apps.security.services import threat_service

POLICY = "/api/v1/security/client-policy/"
EDGE = "/api/v1/security/edge-signals/"
SIGNALS = "/api/v1/security/client-signals/"
SUMMARY = "/api/v1/admin/security/summary/"
VOCAB = "/api/v1/admin/security/vocabulary/"
EVENTS = "/api/v1/admin/security/events/"
PROFILES = "/api/v1/admin/security/profiles/"

BROWSER = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131.0"

# These tests drive the API from the test client's own address, so it must
# not be on the trusted list or nothing would ever be recorded.
NOT_TRUSTED = override_settings(SECURITY_TRUSTED_IPS=[])


@NOT_TRUSTED
class ClientPolicyApiTests(TestCase):
    """The env-driven policy the browser guard obeys."""

    def setUp(self) -> None:
        cache.clear()

    @override_settings(SECURITY_CLIENT_GUARD_MODE="deter")
    def test_the_policy_is_readable_without_signing_in(self) -> None:
        response = self.client.get(POLICY, HTTP_USER_AGENT=BROWSER)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["guard_mode"], "deter")

    @override_settings(SECURITY_CLIENT_GUARD_MODE="off")
    def test_the_guard_can_be_switched_off_from_the_environment(self) -> None:
        self.assertEqual(
            self.client.get(POLICY, HTTP_USER_AGENT=BROWSER).json()["guard_mode"],
            "off",
        )

    @override_settings(SECURITY_CLIENT_GUARD_MODE="ENABLE_EVERYTHING")
    def test_an_unrecognised_mode_falls_back_to_off_not_on(self) -> None:
        # A typo in an env var must never turn a user-hostile mode on.
        self.assertEqual(
            self.client.get(POLICY, HTTP_USER_AGENT=BROWSER).json()["guard_mode"],
            "off",
        )

    @override_settings(SECURITY_GUARD_EXEMPT_AUTHENTICATED=True)
    def test_the_policy_states_the_signed_in_exemption(self) -> None:
        body = self.client.get(POLICY, HTTP_USER_AGENT=BROWSER).json()
        self.assertTrue(body["exempt_authenticated"])
        self.assertEqual(
            set(body), {"guard_mode", "exempt_authenticated", "report_signals"}
        )


@NOT_TRUSTED
class ClientSignalApiTests(TestCase):
    """The one endpoint an anonymous attacker can post to on purpose."""

    def setUp(self) -> None:
        cache.clear()

    def test_a_browser_can_report_a_devtools_signal(self) -> None:
        response = self.client.post(
            SIGNALS,
            {"kind": "devtools_opened", "path": "/recipes"},
            content_type="application/json",
            HTTP_USER_AGENT=BROWSER,
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.json()["recorded"])
        event = SecurityEvent.objects.get(kind=SignalKind.DEVTOOLS_OPENED)
        self.assertEqual(event.path, "/recipes")

    def test_a_client_cannot_report_a_server_only_kind(self) -> None:
        response = self.client.post(
            SIGNALS,
            {"kind": "scanner_agent"},
            content_type="application/json",
            HTTP_USER_AGENT=BROWSER,
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(
            SecurityEvent.objects.filter(kind=SignalKind.SCANNER_AGENT).exists()
        )

    def test_a_client_cannot_choose_the_address_the_event_lands_on(self) -> None:
        # `ip` is not a declared field, and StrictSerializer rejects the
        # whole request rather than quietly ignoring the extra key.
        response = self.client.post(
            SIGNALS,
            {"kind": "devtools_opened", "ip": "203.0.113.200"},
            content_type="application/json",
            HTTP_USER_AGENT=BROWSER,
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(ThreatProfile.objects.filter(ip="203.0.113.200").exists())

    def test_the_detail_map_is_bounded(self) -> None:
        response = self.client.post(
            SIGNALS,
            {
                "kind": "devtools_opened",
                "detail": {f"k{index}": "v" for index in range(20)},
            },
            content_type="application/json",
            HTTP_USER_AGENT=BROWSER,
        )
        self.assertEqual(response.status_code, 400)

    def test_the_response_never_tells_the_caller_its_own_score(self) -> None:
        body = self.client.post(
            SIGNALS,
            {"kind": "devtools_opened"},
            content_type="application/json",
            HTTP_USER_AGENT=BROWSER,
        ).json()

        self.assertEqual(set(body), {"recorded"})

    @override_settings(SECURITY_CLIENT_REPORTS_ENABLED=False)
    def test_ingest_can_be_switched_off_without_erroring_the_client(self) -> None:
        response = self.client.post(
            SIGNALS,
            {"kind": "devtools_opened"},
            content_type="application/json",
            HTTP_USER_AGENT=BROWSER,
        )

        self.assertEqual(response.status_code, 201)
        self.assertFalse(response.json()["recorded"])
        self.assertEqual(SecurityEvent.objects.count(), 0)


@NOT_TRUSTED
class EdgeSignalApiTests(TestCase):
    """The one endpoint that may record somebody else's address."""

    payload = {
        "kind": "honeypot_path",
        "ip": "203.0.113.55",
        "path": "/.env",
        "user_agent": "python-requests/2.31",
    }

    def setUp(self) -> None:
        cache.clear()

    def _post(self, secret: str | None = None, **overrides: object):
        headers = {"HTTP_USER_AGENT": BROWSER}
        if secret is not None:
            headers["HTTP_X_KB_EDGE_SECRET"] = secret
        return self.client.post(
            EDGE,
            {**self.payload, **overrides},
            content_type="application/json",
            **headers,
        )

    def test_the_endpoint_does_not_exist_until_a_secret_is_configured(self) -> None:
        # Default deployment: forwarding off. A 403 here would confirm the
        # route to a scanner; a 404 says nothing.
        self.assertEqual(self._post("anything").status_code, 404)

    @override_settings(SECURITY_INGEST_SECRET="s3cret-edge-token")
    def test_the_wrong_secret_records_nothing(self) -> None:
        response = self._post("not-the-secret")

        self.assertEqual(response.status_code, 403)
        self.assertFalse(ThreatProfile.objects.filter(ip="203.0.113.55").exists())

    @override_settings(SECURITY_INGEST_SECRET="s3cret-edge-token")
    def test_a_missing_secret_records_nothing(self) -> None:
        self.assertEqual(self._post().status_code, 403)
        self.assertEqual(SecurityEvent.objects.count(), 0)

    @override_settings(SECURITY_INGEST_SECRET="s3cret-edge-token")
    def test_the_visitors_address_is_recorded_not_the_edges(self) -> None:
        response = self._post("s3cret-edge-token")

        self.assertEqual(response.status_code, 201)
        event = SecurityEvent.objects.get()
        self.assertEqual(event.ip, "203.0.113.55")
        self.assertEqual(event.kind, SignalKind.HONEYPOT_PATH)
        self.assertEqual(event.method, "EDGE")

    @override_settings(SECURITY_INGEST_SECRET="s3cret-edge-token")
    def test_the_edge_cannot_report_a_windowed_kind(self) -> None:
        # Sweeps and floods are counted per process; letting the edge
        # report them too would double-count the same behaviour.
        response = self._post("s3cret-edge-token", kind="not_found_sweep")
        self.assertEqual(response.status_code, 400)


@NOT_TRUSTED
class AdminAccessTests(TestCase):
    """Who may read the dashboard."""

    def setUp(self) -> None:
        cache.clear()
        users = get_user_model().objects
        self.learner = users.create_user(
            username="learner",
            email="learner@kawaiibake.local",
            password="Kawaii!Chef2026",
        )
        self.staff = users.create_user(
            username="secops",
            email="secops@kawaiibake.local",
            password="Kawaii!Chef2026",
            is_staff=True,
        )

    def test_anonymous_callers_are_rejected(self) -> None:
        for url in (SUMMARY, EVENTS, PROFILES, VOCAB):
            with self.subTest(url=url):
                self.assertIn(
                    self.client.get(url, HTTP_USER_AGENT=BROWSER).status_code,
                    (401, 403),
                )

    def test_an_ordinary_signed_in_learner_is_rejected(self) -> None:
        self.client.force_login(self.learner)
        for url in (SUMMARY, EVENTS, PROFILES, VOCAB):
            with self.subTest(url=url):
                self.assertEqual(
                    self.client.get(url, HTTP_USER_AGENT=BROWSER).status_code, 403
                )

    def test_staff_may_read_every_dashboard_endpoint(self) -> None:
        self.client.force_login(self.staff)
        for url in (SUMMARY, EVENTS, PROFILES, VOCAB):
            with self.subTest(url=url):
                self.assertEqual(
                    self.client.get(url, HTTP_USER_AGENT=BROWSER).status_code, 200
                )


@NOT_TRUSTED
class AdminReadTests(TestCase):
    """What the dashboard shows."""

    def setUp(self) -> None:
        cache.clear()
        self.staff = get_user_model().objects.create_user(
            username="secops",
            email="secops@kawaiibake.local",
            password="Kawaii!Chef2026",
            is_staff=True,
        )
        self.client.force_login(self.staff)

        threat_service.record(
            kind=SignalKind.SCANNER_AGENT,
            ip="198.51.100.30",
            user_agent="sqlmap/1.7",
            path="/api/v1/recipes/",
        )
        threat_service.record(
            kind=SignalKind.AUTOMATION_AGENT,
            ip="198.51.100.31",
            user_agent="curl/8.4.0",
            path="/api/v1/courses/",
        )

    def test_the_summary_counts_profiles_by_band(self) -> None:
        body = self.client.get(SUMMARY, HTTP_USER_AGENT=BROWSER).json()

        self.assertEqual(body["profiles_total"], 2)
        self.assertEqual(body["profiles_by_level"][ThreatLevel.HIGH], 1)
        self.assertEqual(body["profiles_by_level"][ThreatLevel.LOW], 1)
        # Every band is present even at zero, so the dashboard renders a
        # stable four-column strip instead of a shifting one.
        self.assertEqual(set(body["profiles_by_level"]), set(ThreatLevel.values))

    def test_the_vocabulary_lists_every_kind_with_a_label(self) -> None:
        body = self.client.get(VOCAB, HTTP_USER_AGENT=BROWSER).json()

        self.assertEqual(len(body["kinds"]), len(SignalKind.values))
        self.assertEqual(len(body["levels"]), 4)
        self.assertTrue(all(row["label"] for row in body["kinds"]))

    def test_events_can_be_filtered_by_kind(self) -> None:
        body = self.client.get(
            EVENTS, {"kind": "scanner_agent"}, HTTP_USER_AGENT=BROWSER
        ).json()

        self.assertEqual(body["count"], 1)
        self.assertEqual(body["results"][0]["ip"], "198.51.100.30")
        self.assertEqual(body["results"][0]["kind_label"], "Known attack tool user agent")

    def test_events_can_be_searched_by_path_and_user_agent(self) -> None:
        body = self.client.get(
            EVENTS, {"search": "curl"}, HTTP_USER_AGENT=BROWSER
        ).json()
        self.assertEqual(body["count"], 1)
        self.assertEqual(body["results"][0]["ip"], "198.51.100.31")

    def test_the_paginators_own_parameters_are_not_unknown_filters(self) -> None:
        # A strict filter serializer must still accept `page`/`page_size`,
        # or every list breaks on page 2.
        for url in (EVENTS, PROFILES):
            with self.subTest(url=url):
                response = self.client.get(
                    url, {"page": 1, "page_size": 50}, HTTP_USER_AGENT=BROWSER
                )
                self.assertEqual(response.status_code, 200)

    def test_an_unknown_filter_value_is_rejected_rather_than_ignored(self) -> None:
        response = self.client.get(
            EVENTS, {"kind": "not_a_kind"}, HTTP_USER_AGENT=BROWSER
        )
        self.assertEqual(response.status_code, 400)

    def test_profiles_are_ordered_worst_first(self) -> None:
        body = self.client.get(PROFILES, HTTP_USER_AGENT=BROWSER).json()

        self.assertEqual(body["results"][0]["ip"], "198.51.100.30")
        self.assertEqual(body["results"][0]["level"], ThreatLevel.HIGH)

    def test_profiles_can_be_filtered_by_level(self) -> None:
        body = self.client.get(
            PROFILES, {"level": "high"}, HTTP_USER_AGENT=BROWSER
        ).json()
        self.assertEqual(body["count"], 1)

    def test_a_profile_row_exposes_both_the_stored_and_the_decayed_score(
        self,
    ) -> None:
        row = self.client.get(PROFILES, HTTP_USER_AGENT=BROWSER).json()["results"][0]
        self.assertIn("score", row)
        self.assertIn("current_score", row)
        self.assertLessEqual(row["current_score"], row["score"])

    def test_the_detail_view_carries_the_evidence(self) -> None:
        profile = ThreatProfile.objects.get(ip="198.51.100.30")
        body = self.client.get(
            f"{PROFILES}{profile.pk}/", HTTP_USER_AGENT=BROWSER
        ).json()

        self.assertEqual(len(body["recent_events"]), 1)
        self.assertEqual(body["recent_events"][0]["kind"], SignalKind.SCANNER_AGENT)

    def test_a_missing_profile_is_a_404_in_the_standard_envelope(self) -> None:
        response = self.client.get(f"{PROFILES}999999/", HTTP_USER_AGENT=BROWSER)

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.json()["error"]["code"], "threat_profile_not_found"
        )

    def test_no_endpoint_leaks_an_email_address(self) -> None:
        # The actor of an event is shown by public handle only.
        threat_service.record(
            kind=SignalKind.DEVTOOLS_OPENED,
            ip="198.51.100.32",
            actor_id=self.staff.id,
        )
        body = self.client.get(EVENTS, HTTP_USER_AGENT=BROWSER).content.decode()

        self.assertIn("secops", body)
        self.assertNotIn("secops@kawaiibake.local", body)


@NOT_TRUSTED
class AdminActionTests(TestCase):
    """Block, unblock and triage."""

    def setUp(self) -> None:
        cache.clear()
        self.staff = get_user_model().objects.create_user(
            username="secops",
            email="secops@kawaiibake.local",
            password="Kawaii!Chef2026",
            is_staff=True,
        )
        self.client.force_login(self.staff)
        threat_service.record(kind=SignalKind.HONEYPOT_PATH, ip="198.51.100.40")
        self.profile = ThreatProfile.objects.get(ip="198.51.100.40")

    def test_staff_can_block_for_a_bounded_window(self) -> None:
        response = self.client.post(
            f"{PROFILES}{self.profile.pk}/block/",
            {"minutes": 30},
            content_type="application/json",
            HTTP_USER_AGENT=BROWSER,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["is_blocked"])
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.blocked_by_id, self.staff.id)

    def test_a_block_cannot_be_made_effectively_permanent(self) -> None:
        response = self.client.post(
            f"{PROFILES}{self.profile.pk}/block/",
            {"minutes": 60 * 24 * 365},
            content_type="application/json",
            HTTP_USER_AGENT=BROWSER,
        )
        self.assertEqual(response.status_code, 400)

    def test_staff_can_lift_a_block(self) -> None:
        ThreatProfile.objects.filter(pk=self.profile.pk).update(
            blocked_until=timezone.now() + timedelta(hours=1)
        )
        response = self.client.delete(
            f"{PROFILES}{self.profile.pk}/block/", HTTP_USER_AGENT=BROWSER
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["is_blocked"])

    def test_reviewing_records_who_decided_and_why(self) -> None:
        response = self.client.post(
            f"{PROFILES}{self.profile.pk}/review/",
            {"state": ReviewState.IGNORED.value, "note": "สำนักงานใช้ VPN ร่วมกัน"},
            content_type="application/json",
            HTTP_USER_AGENT=BROWSER,
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["review_state"], ReviewState.IGNORED)
        self.assertEqual(body["reviewed_by_handle"], "secops")
        self.assertEqual(body["note"], "สำนักงานใช้ VPN ร่วมกัน")

    def test_a_profile_cannot_be_reset_to_open_through_the_api(self) -> None:
        # Reopening is an automatic consequence of fresh activity, never
        # an operator action  otherwise the queue could be silenced.
        response = self.client.post(
            f"{PROFILES}{self.profile.pk}/review/",
            {"state": ReviewState.OPEN.value},
            content_type="application/json",
            HTTP_USER_AGENT=BROWSER,
        )
        self.assertEqual(response.status_code, 400)

    def test_an_ordinary_learner_cannot_block_anyone(self) -> None:
        learner = get_user_model().objects.create_user(
            username="learner2",
            email="learner2@kawaiibake.local",
            password="Kawaii!Chef2026",
        )
        self.client.force_login(learner)
        response = self.client.post(
            f"{PROFILES}{self.profile.pk}/block/",
            {"minutes": 30},
            content_type="application/json",
            HTTP_USER_AGENT=BROWSER,
        )

        self.assertEqual(response.status_code, 403)
        self.profile.refresh_from_db()
        self.assertIsNone(self.profile.blocked_until)
