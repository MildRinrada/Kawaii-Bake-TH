"""The watcher on the request path: what it records, and what it costs."""

from __future__ import annotations

from datetime import timedelta

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.security.constants import SignalKind, ThreatLevel
from apps.security.models import SecurityEvent, ThreatProfile

RECIPES = "/api/v1/recipes/"
BROWSER = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0 Safari/537.36"
)

# The suite's own address must not be on the trusted list, or nothing here
# would ever be scored.
NOT_TRUSTED = override_settings(SECURITY_TRUSTED_IPS=[])


@NOT_TRUSTED
class ObservationTests(TestCase):
    """Detection through the real middleware stack."""

    def setUp(self) -> None:
        cache.clear()

    def test_a_trap_path_is_recorded_and_still_404s(self) -> None:
        response = self.client.get("/.env", HTTP_USER_AGENT=BROWSER)

        self.assertEqual(response.status_code, 404)
        event = SecurityEvent.objects.get()
        self.assertEqual(event.kind, SignalKind.HONEYPOT_PATH)
        self.assertEqual(event.path, "/.env")
        # The trap must look exactly like any other missing page: a
        # bespoke response would tell the scanner it had been spotted.
        self.assertNotIn(b"security", response.content.lower())

    def test_a_scripted_client_on_a_real_endpoint_is_recorded(self) -> None:
        self.client.get(RECIPES, HTTP_USER_AGENT="curl/8.4.0")

        event = SecurityEvent.objects.get()
        self.assertEqual(event.kind, SignalKind.AUTOMATION_AGENT)
        self.assertEqual(event.path, RECIPES)

    def test_an_sqli_query_string_is_recorded_with_its_marker(self) -> None:
        self.client.get(
            RECIPES, {"search": "x' UNION SELECT password"}, HTTP_USER_AGENT=BROWSER
        )

        event = SecurityEvent.objects.get()
        self.assertEqual(event.kind, SignalKind.SQLI_PROBE)
        self.assertEqual(event.detail["marker"], "union select")

    def test_ordinary_browsing_records_nothing_at_all(self) -> None:
        for _ in range(5):
            self.client.get(RECIPES, {"page": 1}, HTTP_USER_AGENT=BROWSER)

        self.assertEqual(SecurityEvent.objects.count(), 0)
        self.assertEqual(ThreatProfile.objects.count(), 0)

    def test_ordinary_browsing_adds_no_database_queries(self) -> None:
        """The cost claim in the middleware docstring, measured.

        A clean request must cost the same with the watcher on as with it
        off. The one query the watcher can add is the blocklist read, and
        that is cached — so the cache is warmed first, exactly as it is in
        a running process after the first request.
        """
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        with override_settings(SECURITY_WATCH_ENABLED=False):
            with CaptureQueriesContext(connection) as baseline:
                self.client.get(RECIPES, HTTP_USER_AGENT=BROWSER)

        self.client.get(RECIPES, HTTP_USER_AGENT=BROWSER)  # warm the blocklist
        with CaptureQueriesContext(connection) as watched:
            self.client.get(RECIPES, HTTP_USER_AGENT=BROWSER)

        self.assertEqual(len(watched), len(baseline))

    def test_a_burst_of_404s_is_recorded_once_not_once_per_request(self) -> None:
        # 12 misses trips the sweep threshold; the 13th must not re-trip it.
        for index in range(13):
            self.client.get(f"/api/v1/recipes/no-such-recipe-{index}/",
                            HTTP_USER_AGENT=BROWSER)

        sweeps = SecurityEvent.objects.filter(kind=SignalKind.NOT_FOUND_SWEEP)
        self.assertEqual(sweeps.count(), 1)
        self.assertEqual(sweeps.get().status_code, 404)

    @override_settings(SECURITY_WATCH_ENABLED=False)
    def test_the_master_switch_disables_the_middleware_entirely(self) -> None:
        self.client.get("/.env", HTTP_USER_AGENT="sqlmap/1.7")
        self.assertEqual(SecurityEvent.objects.count(), 0)

    @override_settings(SECURITY_TRUSTED_IPS=["127.0.0.1"])
    def test_a_trusted_address_is_not_watched(self) -> None:
        self.client.get("/.env", HTTP_USER_AGENT="sqlmap/1.7")
        self.assertEqual(SecurityEvent.objects.count(), 0)


@NOT_TRUSTED
class BlockEnforcementTests(TestCase):
    """Blocking, and the two ways it is deliberately limited."""

    def setUp(self) -> None:
        cache.clear()
        ThreatProfile.objects.create(
            ip="127.0.0.1",
            score=200,
            level=ThreatLevel.CRITICAL,
            last_seen_at=timezone.now(),
            blocked_until=timezone.now() + timedelta(minutes=30),
        )

    def test_a_blocked_address_gets_the_standard_error_envelope(self) -> None:
        response = self.client.get(RECIPES, HTTP_USER_AGENT=BROWSER)

        self.assertEqual(response.status_code, 403)
        body = response.json()
        self.assertEqual(body["error"]["code"], "request_blocked")
        self.assertIn("request_id", body["error"])

    def test_a_lapsed_block_lets_traffic_through_again(self) -> None:
        ThreatProfile.objects.update(
            blocked_until=timezone.now() - timedelta(minutes=1)
        )
        cache.clear()

        response = self.client.get(RECIPES, HTTP_USER_AGENT=BROWSER)
        self.assertEqual(response.status_code, 200)

    @override_settings(SECURITY_BLOCKING_ENABLED=False)
    def test_blocking_can_be_observed_only_without_being_enforced(self) -> None:
        cache.clear()
        response = self.client.get(RECIPES, HTTP_USER_AGENT=BROWSER)
        self.assertEqual(response.status_code, 200)

    def test_writing_a_block_invalidates_the_cached_blocklist(self) -> None:
        from apps.security.services import threat_service

        # Warm the cache with the blocked state, then lift the block.
        self.assertEqual(self.client.get(RECIPES).status_code, 403)
        profile = ThreatProfile.objects.get(ip="127.0.0.1")
        threat_service.unblock(profile_id=profile.pk, actor_id=None)

        # No sleep: the repository drops the cache on write, so the very
        # next request must already see the change.
        self.assertEqual(
            self.client.get(RECIPES, HTTP_USER_AGENT=BROWSER).status_code, 200
        )
