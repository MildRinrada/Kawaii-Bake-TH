"""API tests for the staff achievements endpoints."""

from __future__ import annotations

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.certificates.constants import AchievementType
from apps.certificates.models import Achievement, BadgeDefinition
from apps.users.tests.factories import create_user


class AdminBadgeApiTests(TestCase):
    """/api/v1/admin/achievements/ and /{slug}/"""

    def setUp(self) -> None:
        self.client = APIClient()
        self.staff = create_user(is_staff=True)
        self.member = create_user()
        self.list_url = reverse("achievements_admin:badges")

    def _detail_url(self, slug: str) -> str:
        return reverse("achievements_admin:badge-detail", kwargs={"slug": slug})

    def test_every_route_requires_staff(self) -> None:
        cases = [
            (None, status.HTTP_401_UNAUTHORIZED),
            (self.member, status.HTTP_403_FORBIDDEN),
        ]
        for user, expected in cases:
            if user:
                self.client.force_login(user)
            self.assertEqual(self.client.get(self.list_url).status_code, expected)
            self.assertEqual(
                self.client.post(self.list_url, {}).status_code, expected
            )
            self.assertEqual(
                self.client.patch(
                    self._detail_url("course_completed"), {}
                ).status_code,
                expected,
            )
            self.client.logout()

    def test_the_list_includes_inactive_badges_and_awarded_counts(self) -> None:
        BadgeDefinition.objects.filter(slug="quiz_master").update(is_active=False)
        Achievement.objects.create(
            user=self.member,
            achievement_type=AchievementType.COURSE_COMPLETED,
            badge=BadgeDefinition.objects.get(slug="course_completed"),
        )
        self.client.force_login(self.staff)

        rows = self.client.get(self.list_url).json()

        by_slug = {row["slug"]: row for row in rows}
        self.assertFalse(by_slug["quiz_master"]["is_active"])
        self.assertEqual(by_slug["course_completed"]["awarded_count"], 1)
        # The public catalogue still hides the deactivated badge.
        public = self.client.get(reverse("achievement_catalog:badges")).json()
        self.assertNotIn("quiz_master", {row["slug"] for row in public})

    def test_create_edit_delete_round_trip(self) -> None:
        self.client.force_login(self.staff)

        created = self.client.post(
            self.list_url,
            {
                "slug": "star-baker",
                "title_th": "นักอบดาวรุ่ง",
                "title_en": "Star Baker",
                "icon": "star-baker",
            },
            format="json",
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        self.assertEqual(created.json()["awarded_count"], 0)

        edited = self.client.patch(
            self._detail_url("star-baker"),
            {"title_th": "สุดยอดนักอบ", "is_active": False},
            format="json",
        )
        self.assertEqual(edited.status_code, status.HTTP_200_OK)
        self.assertEqual(edited.json()["title_th"], "สุดยอดนักอบ")

        deleted = self.client.delete(self._detail_url("star-baker"))
        self.assertEqual(deleted.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(
            BadgeDefinition.objects.filter(slug="star-baker").exists()
        )

    def test_duplicate_slug_is_a_conflict(self) -> None:
        self.client.force_login(self.staff)

        response = self.client.post(
            self.list_url,
            {"slug": "course_completed", "title_th": "ซ้ำ", "title_en": "Dup"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.json()["error"]["code"], "duplicate_badge_slug")

    def test_an_awarded_badge_cannot_be_deleted(self) -> None:
        badge = BadgeDefinition.objects.get(slug="first_course")
        Achievement.objects.create(
            user=self.member,
            achievement_type=AchievementType.FIRST_COURSE,
            badge=badge,
        )
        self.client.force_login(self.staff)

        response = self.client.delete(self._detail_url("first_course"))

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.json()["error"]["code"], "badge_in_use")
        self.assertTrue(
            BadgeDefinition.objects.filter(slug="first_course").exists()
        )


class AdminAwardApiTests(TestCase):
    """GET /api/v1/admin/achievements/awards/"""

    def setUp(self) -> None:
        self.client = APIClient()
        self.staff = create_user(is_staff=True)
        self.earner = create_user(username="prizewinner")
        Achievement.objects.create(
            user=self.earner,
            achievement_type=AchievementType.COURSE_COMPLETED,
            badge=BadgeDefinition.objects.get(slug="course_completed"),
        )
        self.url = reverse("achievements_admin:awards")

    def test_the_ledger_lists_awards_with_the_earner(self) -> None:
        self.client.force_login(self.staff)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rows = response.json()["results"]
        self.assertEqual(rows[0]["username"], "prizewinner")
        self.assertEqual(rows[0]["badge"]["slug"], "course_completed")

    def test_search_narrows_by_earner(self) -> None:
        self.client.force_login(self.staff)

        hits = self.client.get(self.url, {"search": "prizewinner"}).json()
        misses = self.client.get(self.url, {"search": "nobody-here"}).json()

        self.assertEqual(hits["count"], 1)
        self.assertEqual(misses["count"], 0)


class AdminCertificateApiTests(TestCase):
    """/api/v1/admin/certificates/ and /{id}/revoke/"""

    def setUp(self) -> None:
        self.client = APIClient()
        self.staff = create_user(is_staff=True)
        self.student = create_user(
            username="certholder", first_name="ชนิดา", last_name="พรหมมา"
        )
        instructor = create_user()
        from apps.certificates.services import certificate_service
        from apps.certificates.tests.factories import build_completed_course

        course = build_completed_course(
            student=self.student, instructor=instructor
        )
        self.certificate, _ = certificate_service.issue_if_completed(
            user_id=self.student.id, course_slug=course.slug
        )
        self.list_url = reverse("certificates_admin:list")
        self.revoke_url = reverse(
            "certificates_admin:revoke",
            kwargs={"certificate_id": self.certificate.id},
        )

    def test_both_routes_require_staff(self) -> None:
        self.assertEqual(
            self.client.get(self.list_url).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.client.force_login(self.student)
        self.assertEqual(
            self.client.get(self.list_url).status_code, status.HTTP_403_FORBIDDEN
        )
        self.assertEqual(
            self.client.post(
                self.revoke_url, {"reason": "x"}, format="json"
            ).status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_the_registry_lists_certificates_with_the_holder(self) -> None:
        self.client.force_login(self.staff)

        payload = self.client.get(self.list_url).json()

        row = payload["results"][0]
        self.assertEqual(row["username"], "certholder")
        self.assertEqual(row["status"], "valid")
        self.assertEqual(
            row["certificate_number"], self.certificate.certificate_number
        )

    def test_search_and_status_filters_narrow_the_registry(self) -> None:
        self.client.force_login(self.staff)

        by_number = self.client.get(
            self.list_url, {"search": self.certificate.certificate_number}
        ).json()
        self.assertEqual(by_number["count"], 1)

        revoked_only = self.client.get(
            self.list_url, {"status": "revoked"}
        ).json()
        self.assertEqual(revoked_only["count"], 0)

    def test_revocation_records_the_actor_and_reason_once(self) -> None:
        self.client.force_login(self.staff)

        first = self.client.post(
            self.revoke_url,
            {"reason": "ออกให้ผิดคน"},
            format="json",
        )
        self.assertEqual(first.status_code, status.HTTP_200_OK)
        payload = first.json()
        self.assertEqual(payload["status"], "revoked")
        self.assertEqual(payload["revoked_by"], self.staff.username)
        self.assertEqual(payload["revoked_reason"], "ออกให้ผิดคน")

        # The public verification answer flips to revoked, not missing.
        verify = self.client.get(
            f"/api/v1/certificates/{self.certificate.verification_token}/"
        )
        self.assertEqual(verify.status_code, status.HTTP_200_OK)
        self.assertEqual(verify.json()["status"], "revoked")

        # A second revocation is a conflict - the first reason stays.
        second = self.client.post(
            self.revoke_url, {"reason": "อีกเหตุผล"}, format="json"
        )
        self.assertEqual(second.status_code, status.HTTP_409_CONFLICT)
        self.certificate.refresh_from_db()
        self.assertEqual(self.certificate.revoked_reason, "ออกให้ผิดคน")

    def test_revoking_without_a_reason_is_rejected(self) -> None:
        self.client.force_login(self.staff)

        response = self.client.post(self.revoke_url, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_revoking_an_unknown_certificate_is_a_404(self) -> None:
        self.client.force_login(self.staff)

        response = self.client.post(
            reverse(
                "certificates_admin:revoke", kwargs={"certificate_id": 999999}
            ),
            {"reason": "x"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class CertificateTemplateApiTests(TestCase):
    """/api/v1/admin/certificates/templates/…"""

    def setUp(self) -> None:
        from apps.courses.tests.factories import create_published_course

        self.client = APIClient()
        self.staff = create_user(is_staff=True)
        self.member = create_user()
        self.course = create_published_course(instructor=create_user())
        self.detail_url = reverse(
            "certificates_admin:template-detail",
            kwargs={"course_slug": self.course.slug},
        )

    def _design(self, **overrides):
        base = {
            "size": {"width": 1123, "height": 794},
            "background": "#fffaf3",
            "elements": [
                {
                    "id": "recipient",
                    "kind": "field",
                    "name": "ชื่อผู้รับ",
                    "field": "recipient_full_name",
                    "x": 100, "y": 100, "w": 700, "h": 60,
                    "rotation": 0, "opacity": 1, "z": 1,
                    "locked": False, "hidden": False,
                    "style": {"fontSize": 40, "align": "center"},
                }
            ],
        }
        base.update(overrides)
        return base

    def test_every_route_requires_staff(self) -> None:
        for user, expected in (
            (None, status.HTTP_401_UNAUTHORIZED),
            (self.member, status.HTTP_403_FORBIDDEN),
        ):
            if user:
                self.client.force_login(user)
            self.assertEqual(
                self.client.get(self.detail_url).status_code, expected
            )
            self.client.logout()

    def test_first_read_seeds_the_default_design(self) -> None:
        self.client.force_login(self.staff)

        payload = self.client.get(self.detail_url).json()

        self.assertEqual(payload["status"], "draft")
        self.assertIsNone(payload["published_design"])
        element_ids = {e["id"] for e in payload["draft_design"]["elements"]}
        self.assertIn("recipient", element_ids)
        self.assertIn("signature-1", element_ids)

    def test_autosave_publish_reset_round_trip(self) -> None:
        self.client.force_login(self.staff)

        saved = self.client.put(
            self.detail_url, {"design": self._design()}, format="json"
        )
        self.assertEqual(saved.status_code, status.HTTP_200_OK)
        self.assertEqual(len(saved.json()["draft_design"]["elements"]), 1)

        published = self.client.post(
            reverse(
                "certificates_admin:template-publish",
                kwargs={"course_slug": self.course.slug},
            )
        )
        self.assertEqual(published.status_code, status.HTTP_200_OK)
        self.assertEqual(published.json()["status"], "published")
        self.assertEqual(
            len(published.json()["published_design"]["elements"]), 1
        )

        # Draft drifts, reset returns it to the published version.
        design = self._design()
        design["elements"] = []
        self.client.put(self.detail_url, {"design": design}, format="json")
        reset = self.client.post(
            reverse(
                "certificates_admin:template-reset",
                kwargs={"course_slug": self.course.slug},
            )
        )
        self.assertEqual(len(reset.json()["draft_design"]["elements"]), 1)

    def test_the_signature_ceiling_is_enforced(self) -> None:
        self.client.force_login(self.staff)
        signature = {
            "kind": "signature",
            "name": "ลายเซ็น",
            "x": 0, "y": 0, "w": 200, "h": 100,
            "rotation": 0, "opacity": 1, "z": 1,
            "locked": False, "hidden": False,
            "signature": {"name": "a", "title": "b", "organization": "", "image": ""},
            "style": {},
        }
        design = self._design(
            elements=[{**signature, "id": f"sig-{i}"} for i in range(4)]
        )

        response = self.client.put(
            self.detail_url, {"design": design}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_field_custom_override_saves_and_is_length_capped(self) -> None:
        """A field may carry a staff override text ("มอบโดย …") - stored
        verbatim within the same cap as free text."""
        self.client.force_login(self.staff)

        design = self._design()
        design["elements"][0]["text"] = "มอบโดย เชฟมิลด์ รินรดา"
        saved = self.client.put(
            self.detail_url, {"design": design}, format="json"
        )
        self.assertEqual(saved.status_code, status.HTTP_200_OK)
        self.assertEqual(
            saved.json()["draft_design"]["elements"][0]["text"],
            "มอบโดย เชฟมิลด์ รินรดา",
        )

        design["elements"][0]["text"] = "ก" * 501
        rejected = self.client.put(
            self.detail_url, {"design": design}, format="json"
        )
        self.assertEqual(rejected.status_code, status.HTTP_400_BAD_REQUEST)

    def test_malformed_documents_are_rejected(self) -> None:
        self.client.force_login(self.staff)
        for design in (
            [],
            {"size": {"width": 1123, "height": 794}, "elements": "nope"},
            self._design(
                elements=[{"id": "x", "kind": "teleporter", "x": 0, "y": 0,
                           "w": 10, "h": 10, "rotation": 0, "opacity": 1,
                           "z": 0, "locked": False, "hidden": False,
                           "style": {}}]
            ),
        ):
            response = self.client.put(
                self.detail_url, {"design": design}, format="json"
            )
            self.assertEqual(
                response.status_code, status.HTTP_400_BAD_REQUEST
            )

    def test_delete_returns_the_course_to_the_default(self) -> None:
        from apps.certificates.models import CertificateTemplate

        self.client.force_login(self.staff)
        self.client.put(self.detail_url, {"design": self._design()}, format="json")

        response = self.client.delete(self.detail_url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(
            CertificateTemplate.objects.filter(course=self.course).exists()
        )

    def test_unknown_course_is_a_404(self) -> None:
        self.client.force_login(self.staff)

        response = self.client.get(
            reverse(
                "certificates_admin:template-detail",
                kwargs={"course_slug": "no-course"},
            )
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_the_workspace_list_shows_existing_rows(self) -> None:
        self.client.force_login(self.staff)
        self.client.put(self.detail_url, {"design": self._design()}, format="json")

        rows = self.client.get(
            reverse("certificates_admin:templates")
        ).json()

        self.assertEqual(rows[0]["course_slug"], self.course.slug)
        self.assertEqual(rows[0]["status"], "draft")
        self.assertEqual(rows[0]["updated_by"], self.staff.username)
