"""API tests for the gallery: endpoints, filters, privacy, no N+1."""

from __future__ import annotations

from django.test import TestCase
from rest_framework.test import APIClient

from apps.gallery.constants import GalleryPostStatus
from apps.gallery.services import gallery_service
from apps.gallery.tests.factories import create_post, make_image_file
from apps.recipes.tests.factories import create_category, create_published_recipe
from apps.users.tests.factories import create_user


class GalleryApiTests(TestCase):
    """The endpoint surface."""

    def setUp(self) -> None:
        self.client = APIClient()
        self.author = create_user(username="gapiauthor")
        self.stranger = create_user(username="gapistranger")

    def test_anonymous_reads_but_cannot_write(self) -> None:
        post = create_post(author=self.author)

        listing = self.client.get("/api/v1/gallery/")
        detail = self.client.get(f"/api/v1/gallery/{post.pk}/")
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(detail.status_code, 200)

        created = self.client.post("/api/v1/gallery/", {"caption": "x"})
        self.assertEqual(created.status_code, 401)

    def test_unpublished_is_404_for_stranger_and_anon(self) -> None:
        hidden = create_post(
            author=self.author, status=GalleryPostStatus.UNPUBLISHED
        )
        self.assertEqual(
            self.client.get(f"/api/v1/gallery/{hidden.pk}/").status_code, 404
        )
        self.client.force_login(self.stranger)
        self.assertEqual(
            self.client.get(f"/api/v1/gallery/{hidden.pk}/").status_code, 404
        )
        listing = self.client.get("/api/v1/gallery/").json()
        self.assertEqual(listing["count"], 0)

    def test_create_upload_and_roundtrip(self) -> None:
        recipe = create_published_recipe(author=self.author, slug="gapi-cake")
        self.client.force_login(self.author)

        created = self.client.post(
            "/api/v1/gallery/",
            {"caption": "ครัวซองต์แรกในชีวิต 🥐", "recipe_id": recipe.id},
            format="json",
        )
        self.assertEqual(created.status_code, 201)
        body = created.json()
        self.assertEqual(body["author_handle"], "gapiauthor")
        self.assertEqual(body["recipe"]["slug"], "gapi-cake")

        uploaded = self.client.post(
            f"/api/v1/gallery/{body['id']}/images/", {"image": make_image_file()}
        )
        self.assertEqual(uploaded.status_code, 201)
        self.assertTrue(uploaded.json()["url"].startswith("http"))

        detail = self.client.get(f"/api/v1/gallery/{body['id']}/").json()
        self.assertEqual(len(detail["images"]), 1)
        self.assertIn("ครัวซองต์แรกในชีวิต", detail["caption"])

    def test_stranger_cannot_mutate(self) -> None:
        post = create_post(author=self.author)
        self.client.force_login(self.stranger)

        patched = self.client.patch(
            f"/api/v1/gallery/{post.pk}/", {"caption": "แอบ"}, format="json"
        )
        deleted = self.client.delete(f"/api/v1/gallery/{post.pk}/")
        uploaded = self.client.post(
            f"/api/v1/gallery/{post.pk}/images/", {"image": make_image_file()}
        )
        self.assertEqual(patched.status_code, 404)
        self.assertEqual(deleted.status_code, 404)
        self.assertEqual(uploaded.status_code, 404)

    def test_unknown_payload_keys_rejected(self) -> None:
        self.client.force_login(self.author)
        response = self.client.post(
            "/api/v1/gallery/", {"captoin": "typo"}, format="json"
        )
        self.assertEqual(response.status_code, 400)

    def test_filters_narrow_only(self) -> None:
        category = create_category(slug="filter-cakes")
        recipe = create_published_recipe(author=self.author, slug="gapi-filter")
        recipe.categories.add(category)
        create_post(author=self.author, recipe=recipe)
        create_post(author=self.stranger)

        by_recipe = self.client.get(f"/api/v1/gallery/?recipe_id={recipe.id}").json()
        by_category = self.client.get("/api/v1/gallery/?category=filter-cakes").json()
        by_author = self.client.get("/api/v1/gallery/?author=gapistranger").json()

        self.assertEqual(by_recipe["count"], 1)
        self.assertEqual(by_category["count"], 1)
        self.assertEqual(by_author["count"], 1)
        self.assertEqual(by_author["results"][0]["author_handle"], "gapistranger")

    def test_no_email_in_public_payload(self) -> None:
        create_post(author=self.author)
        body = str(self.client.get("/api/v1/gallery/").json())
        self.assertNotIn(self.author.email, body)
        self.assertIn("gapiauthor", body)

    def test_list_query_count_is_flat(self) -> None:
        for index in range(6):
            post = create_post(author=self.author)
            gallery_service.add_image(
                post_id=post.pk,
                viewer_id=self.author.id,
                image=make_image_file(name=f"b{index}.png"),
            )
        # count + page + images prefetch  flat regardless of rows.
        with self.assertNumQueries(3):
            response = self.client.get("/api/v1/gallery/")
        self.assertEqual(response.json()["count"], 6)
