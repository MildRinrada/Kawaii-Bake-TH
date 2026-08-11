"""API tests for the staff notification endpoints."""

from __future__ import annotations

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.notifications.constants import NotificationEventType
from apps.notifications.models import Notification, NotificationPreference
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
            {"title": "ปิดปรับปรุงระบบคืนนี้", "body": "ตีสองถึงตีสาม"},
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
