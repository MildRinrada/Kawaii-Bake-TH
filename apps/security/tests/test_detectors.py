"""Detector rules — pure string tests, no database, no HTTP.

The rules are the part of this app most likely to be wrong in a way that
matters: a false positive scores a real learner, a false negative misses
a scan. Both directions are asserted here.
"""

from __future__ import annotations

from django.test import SimpleTestCase

from apps.security.constants import SignalKind
from apps.security.detectors import request_rules


class PathRuleTests(SimpleTestCase):
    """What :func:`check_path` does and does not flag."""

    def test_a_trap_path_is_flagged_with_the_trap_that_matched(self) -> None:
        signal = request_rules.check_path("/.env")
        self.assertIsNotNone(signal)
        self.assertEqual(signal.kind, SignalKind.HONEYPOT_PATH)
        self.assertEqual(signal.detail["trap"], "/.env")

    def test_a_trap_prefix_catches_the_whole_scan_family(self) -> None:
        # /wp-admin/setup-config.php is the same scan as /wp-admin.
        signal = request_rules.check_path("/wp-admin/setup-config.php")
        self.assertEqual(signal.kind, SignalKind.HONEYPOT_PATH)

    def test_trap_matching_is_case_insensitive(self) -> None:
        self.assertEqual(
            request_rules.check_path("/WP-Login.PHP").kind,
            SignalKind.HONEYPOT_PATH,
        )

    def test_a_backup_extension_is_a_sensitive_file_probe(self) -> None:
        signal = request_rules.check_path("/media/dump.sql")
        self.assertEqual(signal.kind, SignalKind.SENSITIVE_FILE_PROBE)
        self.assertEqual(signal.detail["suffix"], ".sql")

    def test_encoded_traversal_is_decoded_before_matching(self) -> None:
        signal = request_rules.check_path("/api/v1/recipes/%2e%2e%2f%2e%2e%2fetc")
        self.assertEqual(signal.kind, SignalKind.PATH_TRAVERSAL)

    def test_traversal_outranks_a_trap_on_the_same_path(self) -> None:
        # Both rules match; the more severe one must win.
        signal = request_rules.check_path("/.env/../../etc/passwd")
        self.assertEqual(signal.kind, SignalKind.PATH_TRAVERSAL)

    def test_ordinary_thai_content_paths_are_not_flagged(self) -> None:
        for path in (
            "/api/v1/recipes/",
            "/api/v1/recipes/%E0%B8%84%E0%B8%B8%E0%B8%81%E0%B8%81%E0%B8%B5%E0%B9%89/",
            "/api/v1/courses/basic-bread/lessons/",
            "/media/recipes/cover.jpg",
        ):
            with self.subTest(path=path):
                self.assertIsNone(request_rules.check_path(path))


class QueryRuleTests(SimpleTestCase):
    """What :func:`check_query` does and does not flag."""

    def test_a_union_select_payload_is_an_sqli_probe(self) -> None:
        signal = request_rules.check_query("search=1%27+UNION+SELECT+password")
        self.assertEqual(signal.kind, SignalKind.SQLI_PROBE)

    def test_a_script_tag_is_an_xss_probe(self) -> None:
        signal = request_rules.check_query("q=%3Cscript%3Ealert(1)%3C/script%3E")
        self.assertEqual(signal.kind, SignalKind.XSS_PROBE)

    def test_an_ordinary_search_query_is_not_flagged(self) -> None:
        # A Thai recipe search with filters — the shape real traffic has.
        self.assertIsNone(
            request_rules.check_query(
                "search=%E0%B8%84%E0%B8%B8%E0%B8%81%E0%B8%81%E0%B8%B5%E0%B9%89"
                "&difficulty=easy&page=2&ordering=-created_at"
            )
        )

    def test_an_empty_query_is_not_flagged(self) -> None:
        self.assertIsNone(request_rules.check_query(""))


class UserAgentRuleTests(SimpleTestCase):
    """Client classification, including the allow-list carve-out."""

    def test_a_named_attack_tool_is_the_worst_agent_signal(self) -> None:
        signal = request_rules.check_user_agent("sqlmap/1.7.2#stable")
        self.assertEqual(signal.kind, SignalKind.SCANNER_AGENT)
        self.assertEqual(signal.detail["marker"], "sqlmap")

    def test_curl_is_only_automation_not_an_attack(self) -> None:
        signal = request_rules.check_user_agent("curl/8.4.0")
        self.assertEqual(signal.kind, SignalKind.AUTOMATION_AGENT)

    def test_an_absent_user_agent_is_its_own_weak_signal(self) -> None:
        self.assertEqual(
            request_rules.check_user_agent("").kind, SignalKind.MISSING_USER_AGENT
        )

    def test_search_engines_are_cleared_before_the_automation_list(self) -> None:
        # Googlebot's UA contains no automation marker, but the ordering
        # is what guarantees a future marker addition cannot score it.
        for agent in (
            "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
            "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)",
            "facebookexternalhit/1.1",
        ):
            with self.subTest(agent=agent):
                self.assertIsNone(request_rules.check_user_agent(agent))

    def test_a_real_browser_is_not_flagged(self) -> None:
        self.assertIsNone(
            request_rules.check_user_agent(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/131.0 Safari/537.36"
            )
        )


class InspectRequestTests(SimpleTestCase):
    """The combined verdict."""

    def test_only_the_single_worst_signal_is_returned(self) -> None:
        # curl fetching /.env with an SQLi query matches three rules; one
        # request must still produce one observation.
        signal = request_rules.inspect_request(
            path="/.env",
            query="id=1' or 1=1",
            user_agent="curl/8.4.0",
        )
        self.assertEqual(signal.kind, SignalKind.SQLI_PROBE)

    def test_an_ordinary_browser_request_produces_nothing(self) -> None:
        self.assertIsNone(
            request_rules.inspect_request(
                path="/api/v1/recipes/",
                query="page=1",
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
            )
        )
