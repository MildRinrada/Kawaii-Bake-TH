"""Service and visibility tests for the gallery."""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.gallery.constants import MAX_IMAGES_PER_POST, GalleryPostStatus
from apps.gallery.exceptions import (
    GalleryPostNotFoundError,
    InvalidGalleryReferenceError,
    InvalidImageOrderError,
)
from apps.gallery.models import GalleryImage, GalleryPost
from apps.gallery.selectors import gallery_selector
from apps.gallery.services import gallery_service
from apps.gallery.tests.factories import create_post, make_image_file
from apps.recipes.constants import RecipeVisibility
from apps.recipes.tests.factories import create_published_recipe, create_recipe
from apps.users.tests.factories import create_user


class VisibilityTests(TestCase):
    """One rule for list and detail."""

    def setUp(self) -> None:
        self.author = create_user(username="galauthor")
        self.stranger = create_user(username="galstranger")
        self.public = create_post(author=self.author)
        self.hidden = create_post(
            author=self.author, status=GalleryPostStatus.UNPUBLISHED
        )

    def test_anonymous_sees_published_only(self) -> None:
        posts = list(gallery_selector.list_posts())
        self.assertEqual([p.pk for p in posts], [self.public.pk])
        self.assertIsNone(gallery_selector.get_post(post_id=self.hidden.pk))

    def test_owner_sees_own_unpublished_in_list_and_detail(self) -> None:
        posts = gallery_selector.list_posts(viewer_id=self.author.id)
        self.assertEqual(posts.count(), 2)
        self.assertIsNotNone(
            gallery_selector.get_post(
                post_id=self.hidden.pk, viewer_id=self.author.id
            )
        )

    def test_stranger_cannot_see_unpublished(self) -> None:
        self.assertIsNone(
            gallery_selector.get_post(
                post_id=self.hidden.pk, viewer_id=self.stranger.id
            )
        )
        posts = gallery_selector.list_posts(viewer_id=self.stranger.id)
        self.assertEqual(posts.count(), 1)


class ReferenceTests(TestCase):
    """Only publicly listed content may be referenced."""

    def setUp(self) -> None:
        self.author = create_user(username="galref")

    def test_public_recipe_reference_accepted(self) -> None:
        recipe = create_published_recipe(author=self.author, slug="gal-cake")
        post = gallery_service.create_post(
            author_id=self.author.id,
            data={"status": GalleryPostStatus.PUBLISHED, "recipe_id": recipe.id},
        )
        self.assertEqual(post.recipe_id, recipe.id)

    def test_private_recipe_reference_rejected(self) -> None:
        secret = create_published_recipe(
            author=self.author,
            slug="gal-secret",
            visibility=RecipeVisibility.PRIVATE,
        )
        with self.assertRaises(InvalidGalleryReferenceError):
            gallery_service.create_post(
                author_id=self.author.id,
                data={
                    "status": GalleryPostStatus.PUBLISHED,
                    "recipe_id": secret.id,
                },
            )

    def test_draft_recipe_reference_rejected(self) -> None:
        draft = create_recipe(author=self.author, slug="gal-draft")
        with self.assertRaises(InvalidGalleryReferenceError):
            gallery_service.create_post(
                author_id=self.author.id,
                data={"status": GalleryPostStatus.PUBLISHED, "recipe_id": draft.id},
            )

    def test_post_survives_recipe_deletion(self) -> None:
        recipe = create_published_recipe(author=self.author, slug="gal-gone")
        post = gallery_service.create_post(
            author_id=self.author.id,
            data={"status": GalleryPostStatus.PUBLISHED, "recipe_id": recipe.id},
        )
        recipe.delete()
        post.refresh_from_db()
        self.assertIsNone(post.recipe_id)


class ImageLifecycleTests(TestCase):
    """Upload, order, capacity and real cleanup."""

    def setUp(self) -> None:
        self.author = create_user(username="galimg")
        self.post = create_post(author=self.author)

    def _upload(self):
        return gallery_service.add_image(
            post_id=self.post.pk, viewer_id=self.author.id, image=make_image_file()
        )

    def test_upload_appends_in_order(self) -> None:
        first = self._upload()
        second = self._upload()
        self.assertEqual([first.position, second.position], [1, 2])

    def test_invalid_upload_leaves_no_file(self) -> None:
        from django.core.files.uploadedfile import SimpleUploadedFile

        fake = SimpleUploadedFile("evil.png", b"not-an-image", "image/png")
        with self.assertRaises(ValidationError):
            gallery_service.add_image(
                post_id=self.post.pk, viewer_id=self.author.id, image=fake
            )
        self.assertEqual(GalleryImage.objects.count(), 0)

    def test_capacity_is_enforced(self) -> None:
        for _ in range(MAX_IMAGES_PER_POST):
            self._upload()
        with self.assertRaises(ValidationError):
            self._upload()

    def test_reorder_requires_exact_set(self) -> None:
        first = self._upload()
        second = self._upload()

        with self.assertRaises(InvalidImageOrderError):
            gallery_service.update_post(
                post_id=self.post.pk,
                viewer_id=self.author.id,
                data={"image_ids": [first.pk]},
            )
        with self.assertRaises(InvalidImageOrderError):
            gallery_service.update_post(
                post_id=self.post.pk,
                viewer_id=self.author.id,
                data={"image_ids": [first.pk, first.pk]},
            )

        gallery_service.update_post(
            post_id=self.post.pk,
            viewer_id=self.author.id,
            data={"image_ids": [second.pk, first.pk]},
        )
        ordered = list(self.post.images.values_list("id", flat=True))
        self.assertEqual(ordered, [second.pk, first.pk])

    def test_delete_image_removes_the_stored_file(self) -> None:
        image = self._upload()
        storage, name = image.image.storage, image.image.name
        self.assertTrue(storage.exists(name))

        gallery_service.remove_image(
            post_id=self.post.pk, image_id=image.pk, viewer_id=self.author.id
        )
        self.assertFalse(storage.exists(name))

    def test_delete_post_cleans_every_file(self) -> None:
        names = []
        for _ in range(2):
            image = self._upload()
            names.append((image.image.storage, image.image.name))

        gallery_service.delete_post(post_id=self.post.pk, viewer_id=self.author.id)

        self.assertFalse(GalleryPost.objects.filter(pk=self.post.pk).exists())
        self.assertEqual(GalleryImage.objects.count(), 0)
        for storage, name in names:
            self.assertFalse(storage.exists(name), f"orphan file: {name}")


class OwnershipTests(TestCase):
    """Strangers mutate nothing; "not yours" is 404."""

    def setUp(self) -> None:
        self.author = create_user(username="galown")
        self.stranger = create_user(username="galownstr")
        self.post = create_post(author=self.author)

    def test_stranger_cannot_update_or_delete(self) -> None:
        with self.assertRaises(GalleryPostNotFoundError):
            gallery_service.update_post(
                post_id=self.post.pk,
                viewer_id=self.stranger.id,
                data={"caption": "แอบแก้"},
            )
        with self.assertRaises(GalleryPostNotFoundError):
            gallery_service.delete_post(
                post_id=self.post.pk, viewer_id=self.stranger.id
            )

    def test_owner_updates_caption_and_status(self) -> None:
        post = gallery_service.update_post(
            post_id=self.post.pk,
            viewer_id=self.author.id,
            data={"caption": "แก้แล้ว", "status": GalleryPostStatus.UNPUBLISHED},
        )
        self.assertEqual(post.caption, "แก้แล้ว")
        self.assertEqual(post.status, GalleryPostStatus.UNPUBLISHED)
