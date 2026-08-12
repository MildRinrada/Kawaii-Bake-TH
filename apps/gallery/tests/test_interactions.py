"""Likes and comments on gallery posts (ADR 0032)."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from apps.gallery.constants import GalleryPostStatus
from apps.gallery.models import GalleryComment, GalleryLike
from apps.gallery.tests.factories import create_post
from apps.notifications.models import Notification

User = get_user_model()


class GalleryInteractionTests(APITestCase):
    """Every interaction endpoint, including the refusals."""

    def setUp(self) -> None:
        """Two accounts and one published post by the first."""
        self.author = User.objects.create_user(
            username="baker", email="baker@example.com", password="Rhubarb!Tart2024"
        )
        self.fan = User.objects.create_user(
            username="fan", email="fan@example.com", password="Rhubarb!Tart2024"
        )
        self.post = create_post(author=self.author)

    def test_liking_is_idempotent_and_counted_live(self) -> None:
        """A second like adds no row, and the feed reports the count."""
        self.client.force_authenticate(self.fan)
        first = self.client.post(f"/api/v1/gallery/{self.post.pk}/like/")
        second = self.client.post(f"/api/v1/gallery/{self.post.pk}/like/")

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json()["like_count"], 1)
        self.assertEqual(GalleryLike.objects.filter(post=self.post).count(), 1)

        feed = self.client.get("/api/v1/gallery/").json()["results"][0]
        self.assertEqual(feed["like_count"], 1)
        self.assertTrue(feed["viewer_has_liked"])

    def test_unliking_removes_the_row_and_the_viewer_flag(self) -> None:
        """Unlike is idempotent too, and the flag follows the viewer."""
        self.client.force_authenticate(self.fan)
        self.client.post(f"/api/v1/gallery/{self.post.pk}/like/")
        response = self.client.delete(f"/api/v1/gallery/{self.post.pk}/like/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["like_count"], 0)
        self.assertFalse(GalleryLike.objects.filter(post=self.post).exists())
        # A second delete is not an error.
        self.assertEqual(
            self.client.delete(f"/api/v1/gallery/{self.post.pk}/like/").status_code,
            200,
        )

    def test_anonymous_sees_counts_but_never_a_liked_flag(self) -> None:
        """The feed is public; the personal flag is not invented for it."""
        GalleryLike.objects.create(post=self.post, user=self.fan)
        feed = self.client.get("/api/v1/gallery/").json()["results"][0]

        self.assertEqual(feed["like_count"], 1)
        self.assertFalse(feed["viewer_has_liked"])

    def test_commenting_notifies_the_author_but_never_yourself(self) -> None:
        """A comment reaches the post's owner; self-comments stay quiet."""
        self.client.force_authenticate(self.fan)
        # `notify` defers delivery to on_commit, which a test transaction
        # never reaches on its own (ADR 0016).
        with self.captureOnCommitCallbacks(execute=True):
            created = self.client.post(
                f"/api/v1/gallery/{self.post.pk}/comments/",
                {"body": "หน้าตาน่ากินมากเลยค่ะ"},
                format="json",
            )
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.json()["author_handle"], "fan")

        notification = Notification.objects.filter(recipient=self.author).first()
        self.assertIsNotNone(notification)
        self.assertEqual(notification.event_type, "gallery_comment")
        self.assertEqual(notification.link, f"/community/posts/{self.post.pk}/")

        self.client.force_authenticate(self.author)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(
                f"/api/v1/gallery/{self.post.pk}/comments/",
                {"body": "ขอบคุณค่ะ"},
                format="json",
            )
        self.assertEqual(Notification.objects.filter(recipient=self.author).count(), 1)

    def test_comment_list_is_public_and_counted_on_the_post(self) -> None:
        """Anyone who can see the post can read its comments."""
        GalleryComment.objects.create(post=self.post, author=self.fan, body="สวยมาก")
        listing = self.client.get(f"/api/v1/gallery/{self.post.pk}/comments/")

        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.json()["count"], 1)
        detail = self.client.get(f"/api/v1/gallery/{self.post.pk}/").json()
        self.assertEqual(detail["comment_count"], 1)

    def test_hidden_post_hides_its_interactions(self) -> None:
        """A post a viewer cannot see 404s for comments and likes alike."""
        hidden = create_post(
            author=self.author, status=GalleryPostStatus.UNPUBLISHED
        )
        self.client.force_authenticate(self.fan)

        self.assertEqual(
            self.client.get(f"/api/v1/gallery/{hidden.pk}/comments/").status_code, 404
        )
        self.assertEqual(
            self.client.post(f"/api/v1/gallery/{hidden.pk}/like/").status_code, 404
        )
        self.assertEqual(
            self.client.post(
                f"/api/v1/gallery/{hidden.pk}/comments/",
                {"body": "แอบดู"},
                format="json",
            ).status_code,
            404,
        )

    def test_comment_deletion_is_author_owner_or_staff_only(self) -> None:
        """A stranger gets the same 404 an absent comment would give."""
        comment = GalleryComment.objects.create(
            post=self.post, author=self.fan, body="อร่อยแน่นอน"
        )
        stranger = User.objects.create_user(
            username="passerby",
            email="passerby@example.com",
            password="Rhubarb!Tart2024",
        )

        self.client.force_authenticate(stranger)
        self.assertEqual(
            self.client.delete(f"/api/v1/gallery/comments/{comment.pk}/").status_code,
            404,
        )
        self.assertTrue(GalleryComment.objects.filter(pk=comment.pk).exists())

        # The post's owner may clear their own wall.
        self.client.force_authenticate(self.author)
        self.assertEqual(
            self.client.delete(f"/api/v1/gallery/comments/{comment.pk}/").status_code,
            204,
        )
        self.assertFalse(GalleryComment.objects.filter(pk=comment.pk).exists())

    def test_interactions_require_a_session(self) -> None:
        """Reading is public; liking and commenting are not."""
        self.assertEqual(
            self.client.post(f"/api/v1/gallery/{self.post.pk}/like/").status_code, 401
        )
        self.assertEqual(
            self.client.post(
                f"/api/v1/gallery/{self.post.pk}/comments/",
                {"body": "ขอลองบ้าง"},
                format="json",
            ).status_code,
            401,
        )

    def test_deleting_a_post_takes_its_interactions_with_it(self) -> None:
        """Likes and comments are leaves - nothing outlives the post."""
        GalleryLike.objects.create(post=self.post, user=self.fan)
        GalleryComment.objects.create(post=self.post, author=self.fan, body="เยี่ยม")

        self.client.force_authenticate(self.author)
        self.assertEqual(
            self.client.delete(f"/api/v1/gallery/{self.post.pk}/").status_code, 204
        )
        self.assertFalse(GalleryLike.objects.exists())
        self.assertFalse(GalleryComment.objects.exists())
