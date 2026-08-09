"""Model-layer tests: the read stamp, preference rules, no content FKs."""

from __future__ import annotations

from django.conf import settings
from django.db import IntegrityError, models, transaction
from django.test import TestCase
from django.utils import timezone

from apps.notifications.constants import NotificationEventType
from apps.notifications.models import Notification, NotificationPreference
from apps.notifications.selectors import notification_selector
from apps.notifications.tests.factories import create_notification
from apps.users.tests.factories import create_user


class NotificationModelTests(TestCase):
    """Snapshot shape and the stamp-once read."""

    def setUp(self) -> None:
        self.user = create_user(username="notifmodel")

    def test_read_at_is_initially_null(self) -> None:
        notification = create_notification(recipient=self.user)
        self.assertIsNone(notification.read_at)

    def test_read_stamp_survives_and_is_once(self) -> None:
        notification = create_notification(recipient=self.user)
        Notification.objects.filter(
            pk=notification.pk, read_at__isnull=True
        ).update(read_at=timezone.now())
        notification.refresh_from_db()
        first_stamp = notification.read_at
        self.assertIsNotNone(first_stamp)

        # The conditional UPDATE matches nothing the second time.
        updated = Notification.objects.filter(
            pk=notification.pk, read_at__isnull=True
        ).update(read_at=timezone.now())
        self.assertEqual(updated, 0)
        notification.refresh_from_db()
        self.assertEqual(notification.read_at, first_stamp)

    def test_no_foreign_key_to_any_content_domain(self) -> None:
        """The snapshot rule, enforced structurally (ADR 0016)."""
        fk_targets = [
            field.related_model._meta.label
            for field in Notification._meta.get_fields()
            if isinstance(field, models.ForeignKey)
        ]
        self.assertEqual(fk_targets, [settings.AUTH_USER_MODEL])

    def test_thai_snapshot_round_trip(self) -> None:
        notification = create_notification(
            recipient=self.user,
            title="มีนักเรียนใหม่ในคอร์สของคุณ",
            body='คุณมายด์ ลงทะเบียนเรียน "คอร์สครัวซองต์" 🥐',
        )
        notification.refresh_from_db()
        self.assertIn("🥐", notification.body)


class PreferenceModelTests(TestCase):
    """Uniqueness and the absent-row default."""

    def setUp(self) -> None:
        self.user = create_user(username="prefmodel")

    def test_one_row_per_user_and_event(self) -> None:
        NotificationPreference.objects.create(
            user=self.user,
            event_type=NotificationEventType.REVIEW_RECEIVED,
            enabled=False,
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            NotificationPreference.objects.create(
                user=self.user,
                event_type=NotificationEventType.REVIEW_RECEIVED,
                enabled=True,
            )

    def test_absent_row_means_enabled(self) -> None:
        self.assertTrue(
            notification_selector.is_event_enabled(
                user_id=self.user.id,
                event_type=NotificationEventType.REVIEW_RECEIVED,
            )
        )
        self.assertEqual(
            notification_selector.effective_preferences(user_id=self.user.id),
            {value: True for value in NotificationEventType.values},
        )

    def test_explicit_opt_out_disables(self) -> None:
        NotificationPreference.objects.create(
            user=self.user,
            event_type=NotificationEventType.COURSE_ENROLLMENT,
            enabled=False,
        )
        self.assertFalse(
            notification_selector.is_event_enabled(
                user_id=self.user.id,
                event_type=NotificationEventType.COURSE_ENROLLMENT,
            )
        )
        # Other event types are untouched by one opt-out.
        self.assertTrue(
            notification_selector.is_event_enabled(
                user_id=self.user.id,
                event_type=NotificationEventType.REVIEW_RECEIVED,
            )
        )
