"""API tests: the feed, read stamps, preferences, privacy, no N+1."""

from __future__ import annotations

from django.test import TestCase
from rest_framework.test import APIClient

from apps.notifications.constants import NotificationEventType
from apps.notifications.services import notification_service
from apps.notifications.tests.factories import create_notification
from apps.users.tests.factories import create_user


class NotificationApiTests(TestCase):
    """The four endpoints, owner-scoped."""

    def setUp(self) -> None:
        self.client = APIClient()
        self.user = create_user(username="napiuser")
        self.stranger = create_user(username="napistranger")

    def test_anonymous_is_denied_everywhere(self) -> None:
        notification = create_notification(recipient=self.user)
        paths = [
            ("get", "/api/v1/me/notifications/"),
            ("post", f"/api/v1/me/notifications/{notification.pk}/read/"),
            ("post", "/api/v1/me/notifications/read-all/"),
            ("get", "/api/v1/me/notifications/preferences/"),
            ("patch", "/api/v1/me/notifications/preferences/"),
        ]
        for method, path in paths:
            with self.subTest(path=path):
                response = getattr(self.client, method)(path)
                self.assertEqual(response.status_code, 401)

    def test_list_is_newest_first_with_unread_count(self) -> None:
        old = create_notification(recipient=self.user, title="เก่า")
        new = create_notification(recipient=self.user, title="ใหม่")
        notification_service.mark_read(
            notification_id=old.pk, user_id=self.user.id
        )
        create_notification(recipient=self.stranger)  # never visible here

        self.client.force_login(self.user)
        response = self.client.get("/api/v1/me/notifications/")
        body = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["count"], 2)
        self.assertEqual(body["unread_count"], 1)
        self.assertEqual(body["results"][0]["id"], new.pk)

    def test_unread_filter(self) -> None:
        read = create_notification(recipient=self.user)
        unread = create_notification(recipient=self.user)
        notification_service.mark_read(
            notification_id=read.pk, user_id=self.user.id
        )

        self.client.force_login(self.user)
        body = self.client.get("/api/v1/me/notifications/?unread=true").json()
        self.assertEqual(body["count"], 1)
        self.assertEqual(body["results"][0]["id"], unread.pk)

    def test_pagination(self) -> None:
        for _ in range(5):
            create_notification(recipient=self.user)
        self.client.force_login(self.user)
        body = self.client.get("/api/v1/me/notifications/?page_size=2").json()
        self.assertEqual(body["count"], 5)
        self.assertEqual(len(body["results"]), 2)
        self.assertIsNotNone(body["next"])

    def test_list_query_count_is_flat(self) -> None:
        for _ in range(8):
            create_notification(recipient=self.user)
        self.client.force_login(self.user)
        # session + user + page count + unread count + page rows.
        with self.assertNumQueries(5):
            response = self.client.get("/api/v1/me/notifications/")
        self.assertEqual(response.json()["count"], 8)

    def test_read_and_idempotent_repeat(self) -> None:
        notification = create_notification(recipient=self.user)
        self.client.force_login(self.user)

        first = self.client.post(
            f"/api/v1/me/notifications/{notification.pk}/read/"
        )
        second = self.client.post(
            f"/api/v1/me/notifications/{notification.pk}/read/"
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(
            first.json()["read_at"], second.json()["read_at"]
        )

    def test_someone_elses_notification_is_404(self) -> None:
        notification = create_notification(recipient=self.user)
        self.client.force_login(self.stranger)
        response = self.client.post(
            f"/api/v1/me/notifications/{notification.pk}/read/"
        )
        self.assertEqual(response.status_code, 404)

    def test_read_all(self) -> None:
        for _ in range(3):
            create_notification(recipient=self.user)
        self.client.force_login(self.user)

        response = self.client.post("/api/v1/me/notifications/read-all/")
        self.assertEqual(response.json()["marked_read"], 3)

        again = self.client.post("/api/v1/me/notifications/read-all/")
        self.assertEqual(again.json()["marked_read"], 0)
        listing = self.client.get("/api/v1/me/notifications/").json()
        self.assertEqual(listing["unread_count"], 0)


class PreferencesApiTests(TestCase):
    """The strict preference surface."""

    def setUp(self) -> None:
        self.client = APIClient()
        self.user = create_user(username="napipref")
        self.client.force_login(self.user)

    def test_get_defaults_every_type_to_enabled(self) -> None:
        body = self.client.get("/api/v1/me/notifications/preferences/").json()
        self.assertEqual(
            body, {value: True for value in NotificationEventType.values}
        )

    def test_patch_updates_and_returns_effective_map(self) -> None:
        response = self.client.patch(
            "/api/v1/me/notifications/preferences/",
            {"review_received": False},
            format="json",
        )
        body = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertFalse(body["review_received"])
        self.assertTrue(body["course_enrollment"])

    def test_unknown_event_type_is_rejected(self) -> None:
        response = self.client.patch(
            "/api/v1/me/notifications/preferences/",
            {"marketing_spam": True},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_non_boolean_value_is_rejected(self) -> None:
        response = self.client.patch(
            "/api/v1/me/notifications/preferences/",
            {"review_received": "maybe"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)


class PrivacyTests(TestCase):
    """The payload never carries private identity."""

    def setUp(self) -> None:
        self.client = APIClient()
        self.author = create_user(username="privauthor")
        self.reviewer = create_user(username="privreviewer")

    def test_notification_payload_never_contains_an_email(self) -> None:
        from apps.recipes.tests.factories import create_published_recipe
        from apps.reviews.services import review_service

        recipe = create_published_recipe(author=self.author, slug="priv-cake")
        with self.captureOnCommitCallbacks(execute=True):
            review_service.create_review(
                user_id=self.reviewer.id,
                kind="recipe",
                slug=recipe.slug,
                data={"rating": 4},
            )

        self.client.force_login(self.author)
        body = self.client.get("/api/v1/me/notifications/").json()

        payload = str(body)
        self.assertNotIn(self.reviewer.email, payload)
        self.assertNotIn(self.author.email, payload)
        self.assertIn("privreviewer", payload)  # the public handle only


class ClickTrackingTests(TestCase):
    """`POST /me/notifications/{id}/click/` - the only click signal there is."""

    def setUp(self) -> None:
        self.client = APIClient()
        self.user = create_user(username="clickuser")
        self.stranger = create_user(username="clickstranger")

    def _click(self, notification_id: int):
        return self.client.post(
            f"/api/v1/me/notifications/{notification_id}/click/"
        )

    def test_click_stamps_once_and_implies_read(self) -> None:
        notification = create_notification(
            recipient=self.user, link="/recipes/khanom-chan/"
        )
        self.client.force_login(self.user)

        first = self._click(notification.pk)
        self.assertEqual(first.status_code, 200)
        body = first.json()
        self.assertIsNotNone(body["clicked_at"])
        # Opening what a notification points at *is* reading it, so one
        # call settles both and the client needs one round trip.
        self.assertIsNotNone(body["read_at"])

        again = self._click(notification.pk)
        self.assertEqual(again.status_code, 200)
        self.assertEqual(again.json()["clicked_at"], body["clicked_at"])

    def test_a_notification_with_no_link_cannot_be_clicked(self) -> None:
        # Accepting it would put clicks in the analytics that no
        # recipient could have made.
        notification = create_notification(recipient=self.user, link="")
        self.client.force_login(self.user)

        response = self._click(notification.pk)

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "not_clickable")

    def test_someone_elses_notification_is_404(self) -> None:
        notification = create_notification(
            recipient=self.stranger, link="/recipes/x/"
        )
        self.client.force_login(self.user)

        response = self._click(notification.pk)

        self.assertEqual(response.status_code, 404)
        notification.refresh_from_db()
        self.assertIsNone(notification.clicked_at)

    def test_anonymous_is_denied(self) -> None:
        notification = create_notification(recipient=self.user, link="/x/")

        self.assertEqual(self._click(notification.pk).status_code, 401)
