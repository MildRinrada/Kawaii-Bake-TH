"""Service-layer tests: delivery contract, preference gate, read stamps."""

from __future__ import annotations

from unittest import mock

from django.db import transaction
from django.test import TestCase

from apps.notifications.constants import NotificationEventType
from apps.notifications.exceptions import NotificationNotFoundError
from apps.notifications.models import Notification, NotificationPreference
from apps.notifications.services import notification_service
from apps.notifications.tests.factories import create_notification
from apps.users.tests.factories import create_user


class NotifyDeliveryTests(TestCase):
    """The on-commit contract and the best-effort guarantee."""

    def setUp(self) -> None:
        self.user = create_user(username="notifysvc")

    def _notify(self, **overrides) -> None:
        payload = {
            "user_id": self.user.id,
            "event_type": NotificationEventType.REVIEW_RECEIVED,
            "title": "มีรีวิวใหม่",
            "body": "รายละเอียด",
            "actor_handle": "somchai",
            "link": "/recipes/x/reviews/",
        }
        payload.update(overrides)
        notification_service.notify(**payload)

    def test_notify_creates_the_snapshot(self) -> None:
        with self.captureOnCommitCallbacks(execute=True):
            self._notify()

        row = Notification.objects.get(recipient=self.user)
        self.assertEqual(row.event_type, "review_received")
        self.assertEqual(row.title, "มีรีวิวใหม่")
        self.assertEqual(row.actor_handle, "somchai")
        self.assertEqual(row.link, "/recipes/x/reviews/")
        self.assertIsNone(row.read_at)

    def test_delivery_waits_for_commit_and_dies_with_rollback(self) -> None:
        """A rolled-back producer transaction must deliver nothing."""
        with self.captureOnCommitCallbacks(execute=True):
            try:
                with transaction.atomic():
                    self._notify()
                    raise RuntimeError("producer failed after notify()")
            except RuntimeError:
                pass
        self.assertEqual(Notification.objects.count(), 0)

    def test_disabled_preference_suppresses_delivery(self) -> None:
        NotificationPreference.objects.create(
            user=self.user,
            event_type=NotificationEventType.REVIEW_RECEIVED,
            enabled=False,
        )
        with self.captureOnCommitCallbacks(execute=True):
            self._notify()
        self.assertEqual(Notification.objects.count(), 0)

    def test_default_is_enabled(self) -> None:
        with self.captureOnCommitCallbacks(execute=True):
            self._notify(event_type=NotificationEventType.ACHIEVEMENT_EARNED)
        self.assertEqual(Notification.objects.count(), 1)

    def test_delivery_failure_is_swallowed_and_logged(self) -> None:
        with mock.patch.object(
            Notification.objects, "create", side_effect=RuntimeError("db down")
        ):
            with self.assertLogs("kawaiibake.notifications", level="ERROR"):
                with self.captureOnCommitCallbacks(execute=True):
                    self._notify()  # must not raise
        self.assertEqual(Notification.objects.count(), 0)


class ReadTests(TestCase):
    """Owner-scoped read stamps."""

    def setUp(self) -> None:
        self.user = create_user(username="readsvc")
        self.stranger = create_user(username="readstranger")

    def test_mark_read_stamps_once_and_is_idempotent(self) -> None:
        notification = create_notification(recipient=self.user)

        first = notification_service.mark_read(
            notification_id=notification.pk, user_id=self.user.id
        )
        self.assertIsNotNone(first.read_at)

        second = notification_service.mark_read(
            notification_id=notification.pk, user_id=self.user.id
        )
        self.assertEqual(second.read_at, first.read_at)

    def test_someone_elses_notification_is_404(self) -> None:
        notification = create_notification(recipient=self.user)
        with self.assertRaises(NotificationNotFoundError):
            notification_service.mark_read(
                notification_id=notification.pk, user_id=self.stranger.id
            )

    def test_mark_all_read_counts_only_newly_stamped(self) -> None:
        for _ in range(3):
            create_notification(recipient=self.user)
        already_read = create_notification(recipient=self.user)
        notification_service.mark_read(
            notification_id=already_read.pk, user_id=self.user.id
        )
        create_notification(recipient=self.stranger)  # untouched

        self.assertEqual(
            notification_service.mark_all_read(user_id=self.user.id), 3
        )
        self.assertEqual(
            notification_service.mark_all_read(user_id=self.user.id), 0
        )
        self.assertEqual(
            Notification.objects.filter(
                recipient=self.stranger, read_at__isnull=True
            ).count(),
            1,
        )


class PreferenceServiceTests(TestCase):
    """Upsert semantics."""

    def setUp(self) -> None:
        self.user = create_user(username="prefsvc")

    def test_set_preferences_touches_only_submitted_types(self) -> None:
        effective = notification_service.set_preferences(
            user_id=self.user.id,
            changes={NotificationEventType.REVIEW_RECEIVED: False},
        )
        self.assertFalse(effective["review_received"])
        self.assertTrue(effective["course_enrollment"])
        # Only the changed row exists — absent still means enabled.
        self.assertEqual(
            NotificationPreference.objects.filter(user=self.user).count(), 1
        )

    def test_set_preferences_is_an_upsert(self) -> None:
        notification_service.set_preferences(
            user_id=self.user.id,
            changes={NotificationEventType.REVIEW_RECEIVED: False},
        )
        effective = notification_service.set_preferences(
            user_id=self.user.id,
            changes={NotificationEventType.REVIEW_RECEIVED: True},
        )
        self.assertTrue(effective["review_received"])
        self.assertEqual(
            NotificationPreference.objects.filter(user=self.user).count(), 1
        )
