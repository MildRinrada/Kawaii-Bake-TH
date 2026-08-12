"""API tests for the staff notification endpoints."""

from __future__ import annotations

from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.notifications.constants import CampaignStatus, NotificationEventType
from apps.notifications.models import (
    Notification,
    NotificationCampaign,
    NotificationPreference,
    NotificationTemplate,
)
from apps.notifications.services import campaign_service, notification_service
from apps.notifications.tests.factories import create_notification
from apps.users.tests.factories import create_user


class AdminNotificationListApiTests(TestCase):
    """GET /api/v1/admin/notifications/"""

    def setUp(self) -> None:
        self.client = APIClient()
        self.staff = create_user(is_staff=True)
        self.member = create_user(username="inboxowner")
        Notification.objects.create(
            recipient=self.member,
            event_type=NotificationEventType.REVIEW_RECEIVED,
            title="มีรีวิวใหม่",
        )

    def test_the_list_requires_staff(self) -> None:
        url = reverse("notifications_admin:list")
        self.assertEqual(
            self.client.get(url).status_code, status.HTTP_401_UNAUTHORIZED
        )
        self.client.force_login(self.member)
        self.assertEqual(
            self.client.get(url).status_code, status.HTTP_403_FORBIDDEN
        )

    def test_the_list_spans_recipients_with_read_state(self) -> None:
        self.client.force_login(self.staff)

        payload = self.client.get(reverse("notifications_admin:list")).json()

        row = payload["results"][0]
        self.assertEqual(row["recipient"], "inboxowner")
        self.assertEqual(row["event_type"], "review_received")
        self.assertIsNone(row["read_at"])

    def test_filters_narrow_by_type_read_state_and_search(self) -> None:
        self.client.force_login(self.staff)
        url = reverse("notifications_admin:list")

        typed = self.client.get(url, {"event_type": "review_received"}).json()
        self.assertEqual(typed["count"], 1)
        self.assertEqual(
            self.client.get(url, {"event_type": "announcement"}).json()["count"],
            0,
        )
        self.assertEqual(self.client.get(url, {"unread": "true"}).json()["count"], 1)
        self.assertEqual(
            self.client.get(url, {"search": "inboxowner"}).json()["count"], 1
        )
        self.assertEqual(
            self.client.get(url, {"nonsense": "x"}).status_code,
            status.HTTP_400_BAD_REQUEST,
        )


class AdminBroadcastApiTests(TestCase):
    """POST /api/v1/admin/notifications/broadcast/"""

    def setUp(self) -> None:
        self.client = APIClient()
        self.staff = create_user(is_staff=True)
        self.member = create_user()
        self.opted_out = create_user()
        NotificationPreference.objects.create(
            user=self.opted_out,
            event_type=NotificationEventType.ANNOUNCEMENT,
            enabled=False,
        )
        self.suspended = create_user(is_active=False)
        self.url = reverse("notifications_admin:broadcast")

    def test_broadcast_requires_staff(self) -> None:
        self.client.force_login(self.member)
        response = self.client.post(self.url, {"title": "x"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_broadcast_reaches_active_opted_in_accounts_only(self) -> None:
        self.client.force_login(self.staff)

        response = self.client.post(
            self.url,
            {
                "title": "ปิดปรับปรุงระบบคืนนี้",
                "body": "ตีสองถึงตีสาม",
                "link": "/support",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # staff + member reached; opted-out and suspended accounts not.
        self.assertEqual(response.json()["recipients"], 2)
        recipients = set(
            Notification.objects.filter(
                event_type=NotificationEventType.ANNOUNCEMENT
            ).values_list("recipient_id", flat=True)
        )
        self.assertEqual(recipients, {self.staff.id, self.member.id})

    def test_broadcast_requires_a_title(self) -> None:
        self.client.force_login(self.staff)

        response = self.client.post(self.url, {"body": "no title"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class CampaignApiTests(TestCase):
    """The campaign lifecycle: compose, estimate, send, analyze (ADR 0030)."""

    def setUp(self) -> None:
        self.client = APIClient()
        self.staff = create_user(username="campaignstaff", is_staff=True)
        self.fan = create_user(username="p16fanmail")
        self.baker = create_user(username="bakerbelle")
        self.url = reverse("notifications_admin:campaigns")

    def _detail(self, campaign_id: int) -> str:
        return reverse(
            "notifications_admin:campaign-detail", args=[campaign_id]
        )

    def test_every_campaign_endpoint_requires_staff(self) -> None:
        self.assertEqual(
            self.client.get(self.url).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.client.force_login(self.fan)
        for method, url in (
            ("get", self.url),
            ("post", self.url),
            ("get", reverse("notifications_admin:stats")),
            ("post", reverse("notifications_admin:audience-estimate")),
            ("get", reverse("notifications_admin:templates")),
        ):
            response = getattr(self.client, method)(url, format="json")
            self.assertEqual(
                response.status_code, status.HTTP_403_FORBIDDEN, url
            )

    def test_create_draft_then_send_resolves_user_name(self) -> None:
        self.client.force_login(self.staff)

        created = self.client.post(
            self.url,
            {
                "kind": "feature",
                "title": "สวัสดี {{user_name}}!",
                "body": "มีของใหม่มาฝาก {{user_name}} ด้วยนะ",
                "cta_text": "ดูเลย",
                "link": "/recipes",
                "audience": {"kind": "specific_users", "usernames": ["p16fanmail"]},
            },
            format="json",
        )

        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        campaign_id = created.json()["id"]
        self.assertEqual(created.json()["status"], "draft")

        sent = self.client.post(
            reverse("notifications_admin:campaign-send", args=[campaign_id])
        )
        self.assertEqual(sent.status_code, status.HTTP_200_OK)
        self.assertEqual(sent.json()["recipients"], 1)

        row = Notification.objects.get(recipient=self.fan)
        self.assertEqual(row.title, "สวัสดี p16fanmail!")
        # The kind travels into the snapshot: it is what the recipient's
        # row draws its glyph and colour from.
        self.assertEqual(row.kind, "feature")
        self.assertEqual(row.cta_text, "ดูเลย")
        self.assertEqual(row.campaign_id, campaign_id)
        self.assertEqual(
            row.event_type, NotificationEventType.ANNOUNCEMENT
        )

    def test_amending_a_sent_campaign_updates_delivered_snapshots(self) -> None:
        """Content edits propagate to every recipient's inbox; the
        audience and schedule stay history."""
        self.client.force_login(self.staff)
        campaign = campaign_service.create_campaign(
            actor_id=self.staff.id,
            audience={"kind": "specific_users", "usernames": ["bakerbelle"]},
            title="ประกาศเดิม {{user_name}}",
            kind="maintenance",
        )
        campaign_service.send_campaign(
            campaign_id=campaign.pk, actor_id=self.staff.id
        )

        amended = self.client.patch(
            self._detail(campaign.pk),
            {"title": "ประกาศแก้แล้วถึง {{user_name}}", "kind": "alert"},
            format="json",
        )
        self.assertEqual(amended.status_code, status.HTTP_200_OK)
        row = Notification.objects.get(recipient=self.baker)
        self.assertEqual(row.title, "ประกาศแก้แล้วถึง bakerbelle")
        self.assertEqual(row.kind, "alert")

        # Audience/schedule of a sent campaign are untouchable, and a
        # sent campaign still cannot be sent again.
        self.assertEqual(
            self.client.patch(
                self._detail(campaign.pk),
                {"audience": {"kind": "all"}},
                format="json",
            ).status_code,
            status.HTTP_409_CONFLICT,
        )
        self.assertEqual(
            self.client.post(
                reverse(
                    "notifications_admin:campaign-send", args=[campaign.pk]
                )
            ).status_code,
            status.HTTP_409_CONFLICT,
        )

    def test_deleting_a_sent_campaign_retracts_its_deliveries(self) -> None:
        """In-app rows make retraction real: the snapshots leave the
        recipients' inboxes together with the campaign."""
        self.client.force_login(self.staff)
        campaign = campaign_service.create_campaign(
            actor_id=self.staff.id,
            audience={"kind": "specific_users", "usernames": ["bakerbelle"]},
            title="ส่งผิด ขออภัย",
        )
        campaign_service.send_campaign(
            campaign_id=campaign.pk, actor_id=self.staff.id
        )
        self.assertEqual(
            Notification.objects.filter(recipient=self.baker).count(), 1
        )

        deleted = self.client.delete(self._detail(campaign.pk))

        self.assertEqual(deleted.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(
            Notification.objects.filter(recipient=self.baker).count(), 0
        )
        self.assertFalse(
            NotificationCampaign.objects.filter(pk=campaign.pk).exists()
        )

    def test_schedule_cancel_and_dispatch(self) -> None:
        self.client.force_login(self.staff)
        future = (timezone.now() + timedelta(hours=2)).isoformat()

        created = self.client.post(
            self.url,
            {
                "title": "นัดหมาย",
                "link": "/recipes",
                "audience": {"kind": "all"},
                "status": "scheduled",
                "scheduled_at": future,
            },
            format="json",
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        campaign_id = created.json()["id"]
        self.assertEqual(created.json()["status"], "scheduled")

        # Not due yet - the dispatcher leaves it alone.
        self.assertEqual(campaign_service.dispatch_due_campaigns(), 0)

        # Walk the clock past the schedule and dispatch for real.
        NotificationCampaign.objects.filter(pk=campaign_id).update(
            scheduled_at=timezone.now() - timedelta(minutes=1)
        )
        self.assertEqual(campaign_service.dispatch_due_campaigns(), 1)
        campaign = NotificationCampaign.objects.get(pk=campaign_id)
        self.assertEqual(campaign.status, CampaignStatus.SENT)
        self.assertEqual(campaign.recipients_count, 3)

        # Canceling only fits scheduled campaigns.
        self.assertEqual(
            self.client.post(
                reverse(
                    "notifications_admin:campaign-cancel", args=[campaign_id]
                )
            ).status_code,
            status.HTTP_409_CONFLICT,
        )

    def test_scheduling_rejects_the_past_and_missing_timestamps(self) -> None:
        self.client.force_login(self.staff)
        past = (timezone.now() - timedelta(hours=1)).isoformat()

        for payload in (
            {
                "title": "x",
                "link": "/recipes",
                "audience": {"kind": "all"},
                "status": "scheduled",
            },
            {
                "title": "x",
                "link": "/recipes",
                "audience": {"kind": "all"},
                "status": "scheduled",
                "scheduled_at": past,
            },
        ):
            response = self.client.post(self.url, payload, format="json")
            self.assertEqual(
                response.status_code, status.HTTP_400_BAD_REQUEST
            )
            self.assertEqual(
                response.json()["error"]["code"], "invalid_schedule"
            )

    def test_unresolvable_variables_block_send_not_draft(self) -> None:
        self.client.force_login(self.staff)

        created = self.client.post(
            self.url,
            {
                "title": "คอร์ส {{course_name}} อัปเดตแล้ว",
                "link": "/courses",
                "audience": {"kind": "all"},
            },
            format="json",
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)

        sent = self.client.post(
            reverse(
                "notifications_admin:campaign-send",
                args=[created.json()["id"]],
            )
        )
        self.assertEqual(sent.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            sent.json()["error"]["code"], "unresolvable_variables"
        )

    def test_estimate_matches_send_and_honours_opt_outs(self) -> None:
        self.client.force_login(self.staff)
        NotificationPreference.objects.create(
            user=self.fan,
            event_type=NotificationEventType.ANNOUNCEMENT,
            enabled=False,
        )
        url = reverse("notifications_admin:audience-estimate")

        everyone = self.client.post(
            url, {"audience": {"kind": "all"}}, format="json"
        )
        self.assertEqual(everyone.status_code, status.HTTP_200_OK)
        # staff + baker; the fan opted out of announcements.
        self.assertEqual(everyone.json()["count"], 2)

        named = self.client.post(
            url,
            {
                "audience": {
                    "kind": "specific_users",
                    "usernames": ["p16fanmail"],
                }
            },
            format="json",
        )
        self.assertEqual(named.json()["count"], 0)

        unknown = self.client.post(
            url,
            {"audience": {"kind": "specific_users", "usernames": ["ghost"]}},
            format="json",
        )
        self.assertEqual(unknown.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            unknown.json()["error"]["code"], "invalid_audience"
        )

        malformed = self.client.post(
            url, {"audience": {"kind": "everyone"}}, format="json"
        )
        self.assertEqual(malformed.status_code, status.HTTP_400_BAD_REQUEST)

    def test_analytics_report_real_read_receipts(self) -> None:
        self.client.force_login(self.staff)
        campaign = campaign_service.create_campaign(
            actor_id=self.staff.id,
            audience={
                "kind": "specific_users",
                "usernames": ["p16fanmail", "bakerbelle"],
            },
            title="วัดผล",
        )
        campaign_service.send_campaign(
            campaign_id=campaign.pk, actor_id=self.staff.id
        )
        Notification.objects.filter(
            recipient=self.fan, campaign=campaign
        ).update(read_at=timezone.now())

        payload = self.client.get(
            reverse(
                "notifications_admin:campaign-analytics", args=[campaign.pk]
            )
        ).json()

        self.assertEqual(payload["recipients"], 2)
        self.assertEqual(payload["delivered"], 2)
        self.assertEqual(payload["read"], 1)
        self.assertEqual(payload["unread"], 1)
        self.assertAlmostEqual(payload["read_rate"], 0.5)

    def test_list_tabs_and_stats_count_honestly(self) -> None:
        self.client.force_login(self.staff)
        campaign_service.create_campaign(
            actor_id=self.staff.id, audience={"kind": "all"}, title="ร่าง"
        )
        sent = campaign_service.create_campaign(
            actor_id=self.staff.id,
            audience={"kind": "specific_users", "usernames": ["bakerbelle"]},
            title="ส่งแล้ว",
        )
        campaign_service.send_campaign(
            campaign_id=sent.pk, actor_id=self.staff.id
        )

        drafts = self.client.get(self.url, {"status": "draft"}).json()
        self.assertEqual(drafts["count"], 1)
        self.assertEqual(drafts["results"][0]["title"], "ร่าง")
        self.assertEqual(
            self.client.get(self.url, {"status": "sent"}).json()["count"], 1
        )

        stats = self.client.get(
            reverse("notifications_admin:stats")
        ).json()
        self.assertEqual(stats["campaigns_sent"], 1)
        self.assertEqual(stats["drafts"], 1)
        self.assertEqual(stats["scheduled"], 0)
        self.assertEqual(stats["sent_today"], 1)
        self.assertEqual(stats["delivered_total"], 1)
        self.assertEqual(stats["read_total"], 0)


class CourseAudienceTests(TestCase):
    """Course-scoped audiences resolve enrollment and {{course_name}}."""

    def setUp(self) -> None:
        from apps.courses.tests.factories import (
            create_published_course,
            enroll_user,
        )

        self.client = APIClient()
        self.staff = create_user(username="courseadmin", is_staff=True)
        self.instructor = create_user(username="chefinstructor")
        self.student = create_user(username="eagerstudent")
        self.dropout = create_user(username="formertaster")
        self.course = create_published_course(
            instructor=self.instructor, title="ครัวซองต์มาสเตอร์"
        )
        enroll_user(user=self.student, course=self.course)
        enroll_user(user=self.dropout, course=self.course, status="dropped")
        self.client.force_login(self.staff)

    def test_enrolled_audience_excludes_dropouts(self) -> None:
        response = self.client.post(
            reverse("notifications_admin:audience-estimate"),
            {
                "audience": {
                    "kind": "course_enrolled",
                    "course_slug": self.course.slug,
                }
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["count"], 1)

        unknown = self.client.post(
            reverse("notifications_admin:audience-estimate"),
            {
                "audience": {
                    "kind": "course_enrolled",
                    "course_slug": "no-such-course",
                }
            },
            format="json",
        )
        self.assertEqual(unknown.status_code, status.HTTP_400_BAD_REQUEST)

    def test_send_fills_course_name_per_recipient(self) -> None:
        campaign = campaign_service.create_campaign(
            actor_id=self.staff.id,
            audience={
                "kind": "course_enrolled",
                "course_slug": self.course.slug,
            },
            title="{{course_name}} มีบทเรียนใหม่",
            body="ไปต่อกันเลย {{user_name}}",
        )
        recipients = campaign_service.send_campaign(
            campaign_id=campaign.pk, actor_id=self.staff.id
        )

        self.assertEqual(recipients, 1)
        row = Notification.objects.get(recipient=self.student)
        self.assertEqual(row.title, "ครัวซองต์มาสเตอร์ มีบทเรียนใหม่")
        self.assertEqual(row.body, "ไปต่อกันเลย eagerstudent")


class TemplateApiTests(TestCase):
    """Composer templates: admin-side configuration, never preferences."""

    def setUp(self) -> None:
        self.client = APIClient()
        self.staff = create_user(is_staff=True)
        self.client.force_login(self.staff)
        self.url = reverse("notifications_admin:templates")

    def test_template_crud_and_archive_round_trip(self) -> None:
        created = self.client.post(
            self.url,
            {
                "name": "ปิดปรับปรุงระบบ",
                "kind": "maintenance",
                "title": "ระบบจะปิดปรับปรุงคืนนี้",
                "body": "{{user_name}} โพสต์ของคุณมีคนถูกใจมากมาย",
            },
            format="json",
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        template_id = created.json()["id"]

        rows = self.client.get(self.url).json()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["kind"], "maintenance")

        archived = self.client.patch(
            reverse(
                "notifications_admin:template-detail", args=[template_id]
            ),
            {"is_archived": True},
            format="json",
        )
        self.assertTrue(archived.json()["is_archived"])

        deleted = self.client.delete(
            reverse(
                "notifications_admin:template-detail", args=[template_id]
            )
        )
        self.assertEqual(deleted.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(NotificationTemplate.objects.count(), 0)

    def test_unknown_template_is_a_404(self) -> None:
        response = self.client.patch(
            reverse("notifications_admin:template-detail", args=[999]),
            {"name": "x"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class AnnouncementKindTests(TestCase):
    """The kind is a closed set, and it travels to the recipient."""

    def setUp(self) -> None:
        self.client = APIClient()
        self.staff = create_user(is_staff=True, username="kindstaff")
        self.reader = create_user(username="kindreader")
        self.client.force_login(self.staff)
        self.url = reverse("notifications_admin:campaigns")

    def _payload(self, **overrides: object) -> dict[str, object]:
        payload: dict[str, object] = {
            "kind": "maintenance",
            "title": "ระบบจะปิดปรับปรุงคืนนี้",
            "body": "ตี 1 ถึงตี 3 ใช้งานไม่ได้ชั่วคราว",
            "link": "/support",
            "audience": {"kind": "specific_users", "usernames": ["kindreader"]},
        }
        payload.update(overrides)
        return payload

    def test_an_unknown_kind_is_rejected(self) -> None:
        # The kind picks the glyph and colour the recipient sees, so a
        # value no client can draw is not a value.
        response = self.client.post(
            self.url, self._payload(kind="post_viral"), format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("kind", response.json()["error"]["details"])

    def test_the_kind_defaults_rather_than_going_blank(self) -> None:
        payload = self._payload()
        del payload["kind"]

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.json()["kind"], "general")

    def test_the_kind_reaches_the_recipients_snapshot(self) -> None:
        created = self.client.post(self.url, self._payload(), format="json")
        campaign_id = created.json()["id"]

        self.client.post(
            reverse("notifications_admin:campaign-send", args=[campaign_id])
        )

        row = Notification.objects.get(recipient=self.reader)
        self.assertEqual(row.kind, "maintenance")
        # And it is a copy, not a join: editing the campaign later must
        # not rewrite what a recipient was told (that is what the amend
        # endpoint is for, deliberately).
        self.assertEqual(row.campaign_id, campaign_id)

    def test_no_free_form_glyph_can_be_smuggled_in(self) -> None:
        response = self.client.post(
            self.url, self._payload(icon="🔥"), format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class CampaignClickAnalyticsTests(TestCase):
    """Click receipts, and the rates they feed."""

    def setUp(self) -> None:
        self.client = APIClient()
        self.staff = create_user(is_staff=True, username="clickstaff")
        self.readers = [
            create_user(username=f"clickreader{index}") for index in range(3)
        ]
        self.client.force_login(self.staff)

    def test_analytics_report_clicks_and_the_rate(self) -> None:
        campaign = campaign_service.create_campaign(
            actor_id=self.staff.id,
            audience={
                "kind": "specific_users",
                "usernames": [user.username for user in self.readers],
            },
            title="ลองสูตรใหม่",
            link="/recipes",
        )
        campaign_service.send_campaign(
            campaign_id=campaign.pk, actor_id=self.staff.id
        )

        # One of the three follows the link; another only opens the list.
        clicker, reader, _ignorer = self.readers
        notification_service.record_click(
            notification_id=Notification.objects.get(recipient=clicker).pk,
            user_id=clicker.id,
        )
        notification_service.mark_read(
            notification_id=Notification.objects.get(recipient=reader).pk,
            user_id=reader.id,
        )

        response = self.client.get(
            reverse(
                "notifications_admin:campaign-analytics", args=[campaign.pk]
            )
        )

        body = response.json()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(body["delivered"], 3)
        self.assertEqual(body["read"], 2)  # the click counts as a read
        self.assertEqual(body["clicked"], 1)
        self.assertAlmostEqual(body["click_rate"], 1 / 3, places=4)
        self.assertAlmostEqual(body["read_rate"], 2 / 3, places=4)

    def test_the_hub_counts_clicks_platform_wide(self) -> None:
        notification = create_notification(
            recipient=self.readers[0], link="/recipes"
        )
        notification_service.record_click(
            notification_id=notification.pk, user_id=self.readers[0].id
        )

        stats = self.client.get(reverse("notifications_admin:stats")).json()

        self.assertEqual(stats["clicked_total"], 1)
