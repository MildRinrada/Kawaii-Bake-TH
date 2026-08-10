"""API tests for the users endpoints."""

from __future__ import annotations

import io
import os

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from PIL import Image
from rest_framework import status
from rest_framework.test import APIClient

from apps.users.constants import COVER_MAX_SIZE_BYTES, BakingCategory, ProfileVisibility
from apps.users.tests.factories import create_user


def make_image_file(
    *,
    name: str = "cover.png",
    image_format: str = "PNG",
    size: tuple[int, int] = (1200, 200),
    compress: bool = True,
) -> SimpleUploadedFile:
    """Build a real, decodable image upload.

    Args:
        name: Client-side filename (used by the server only for its extension).
        image_format: Pillow format to encode as.
        size: Pixel dimensions.
        compress: When ``False``, fills the image with random noise and skips
            PNG compression, so the encoded file is genuinely large. That is
            what makes a size-limit test exercise the size limit instead of
            tripping the corrupt-image check first.

    Returns:
        An uploadable file containing a valid image.
    """
    buffer = io.BytesIO()
    if compress:
        image = Image.new("RGB", size, color="white")
        image.save(buffer, format=image_format)
    else:
        image = Image.frombytes("RGB", size, os.urandom(size[0] * size[1] * 3))
        image.save(buffer, format=image_format, compress_level=0)
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type="image/png")


class ProfileApiTests(TestCase):
    """Owner-facing profile endpoints."""

    def setUp(self) -> None:
        cache.clear()
        self.client = APIClient()
        self.user = create_user(username="baker")

    def test_profile_requires_authentication(self) -> None:
        response = self.client.get(reverse("users:profile"))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.json()["error"]["code"], "not_authenticated")

    def test_owner_can_read_own_profile(self) -> None:
        self.client.force_login(self.user)

        response = self.client.get(reverse("users:profile"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["username"], "baker")
        self.assertEqual(response.json()["email"], self.user.email)

    def test_own_profile_exposes_exactly_the_expected_keys(self) -> None:
        self.client.force_login(self.user)

        response = self.client.get(reverse("users:profile"))

        self.assertEqual(
            set(response.json()),
            {
                "avatar_url",
                "cover_url",
                "username",
                "email",
                "is_email_verified",
                "joined_at",
                "display_name",
                "bio",
                "birthday",
                "location",
                "experience_level",
                "favorite_categories",
            },
        )

    def test_owner_can_update_profile(self) -> None:
        self.client.force_login(self.user)

        response = self.client.patch(
            reverse("users:profile_update"),
            {"bio": "Sourdough obsessive.", "favorite_categories": [BakingCategory.BREAD]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["bio"], "Sourdough obsessive.")
        self.assertEqual(response.json()["favorite_categories"], ["bread"])

    def test_update_rejects_unknown_field(self) -> None:
        self.client.force_login(self.user)

        response = self.client.patch(
            reverse("users:profile_update"),
            {"favourite_categories": ["bread"]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()["error"]["code"], "validation_error")
        self.assertIn("favourite_categories", response.json()["error"]["details"])

    def test_update_rejects_invalid_category(self) -> None:
        self.client.force_login(self.user)

        response = self.client.patch(
            reverse("users:profile_update"),
            {"favorite_categories": ["pizza"]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_cannot_escalate_privileges(self) -> None:
        self.client.force_login(self.user)

        response = self.client.patch(
            reverse("users:profile_update"), {"is_staff": True}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_staff)


class PreferenceApiTests(TestCase):
    """Private preference endpoints."""

    def setUp(self) -> None:
        cache.clear()
        self.client = APIClient()
        self.user = create_user()

    def test_requires_authentication(self) -> None:
        response = self.client.get(reverse("users:preferences"))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_owner_can_read_and_update(self) -> None:
        self.client.force_login(self.user)

        read = self.client.get(reverse("users:preferences"))
        self.assertEqual(read.status_code, status.HTTP_200_OK)

        updated = self.client.patch(
            reverse("users:preferences"),
            {"profile_visibility": ProfileVisibility.PRIVATE, "show_location": False},
            format="json",
        )

        self.assertEqual(updated.status_code, status.HTTP_200_OK)
        self.assertEqual(updated.json()["profile_visibility"], "private")
        self.assertFalse(updated.json()["show_location"])

    def test_invalid_visibility_is_rejected(self) -> None:
        self.client.force_login(self.user)

        response = self.client.patch(
            reverse("users:preferences"), {"profile_visibility": "cosmic"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class PublicProfileApiTests(TestCase):
    """Public profile endpoint and its privacy behaviour."""

    def setUp(self) -> None:
        cache.clear()
        self.client = APIClient()
        self.owner = create_user(username="owner")
        self.stranger = create_user(username="stranger")

    def _url(self, username: str = "owner") -> str:
        return reverse("users:public_profile", kwargs={"username": username})

    def test_public_profile_readable_by_anonymous(self) -> None:
        response = self.client.get(self._url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["username"], "owner")

    def test_public_payload_exposes_exactly_the_expected_keys(self) -> None:
        # Guards against a future field leaking into the public payload.
        response = self.client.get(self._url())

        self.assertEqual(
            set(response.json()),
            {
                "avatar_url",
                "username",
                "display_name",
                "bio",
                "experience_level",
                "favorite_categories",
                "location",
                "birthday",
                "joined_at",
            },
        )

    def test_public_payload_never_contains_private_fields(self) -> None:
        response = self.client.get(self._url())

        for forbidden in ("email", "is_staff", "password", "profile_visibility"):
            self.assertNotIn(forbidden, response.json())

    def test_private_profile_returns_404_not_403(self) -> None:
        preference = self.owner.preference
        preference.profile_visibility = ProfileVisibility.PRIVATE
        preference.save(update_fields=["profile_visibility"])
        self.client.force_login(self.stranger)

        response = self.client.get(self._url())

        # 403 would confirm the account exists; 404 keeps it an unknown.
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unknown_username_returns_404(self) -> None:
        response = self.client.get(self._url("ghost"))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_members_only_profile_hidden_from_anonymous(self) -> None:
        preference = self.owner.preference
        preference.profile_visibility = ProfileVisibility.MEMBERS
        preference.save(update_fields=["profile_visibility"])

        anonymous = self.client.get(self._url())
        self.assertEqual(anonymous.status_code, status.HTTP_404_NOT_FOUND)

        self.client.force_login(self.stranger)
        member = self.client.get(self._url())
        self.assertEqual(member.status_code, status.HTTP_200_OK)


class AccountDeactivationApiTests(TestCase):
    """Account deactivation ends the session and blocks sign-in."""

    def setUp(self) -> None:
        cache.clear()
        self.client = APIClient()
        self.user = create_user()

    def test_deactivate_requires_authentication(self) -> None:
        response = self.client.post(reverse("users:account_deactivate"))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_deactivate_disables_account_and_session(self) -> None:
        self.client.force_login(self.user)

        response = self.client.post(reverse("users:account_deactivate"))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)

        follow_up = self.client.get(reverse("users:profile"))
        self.assertEqual(follow_up.status_code, status.HTTP_401_UNAUTHORIZED)


class ProfileCoverApiTests(TestCase):
    """PATCH /api/v1/users/profile/update/ — the cover banner.

    The browser crops before uploading, so these tests assert the parts that
    survive a hostile client: the bytes are validated, the URL comes back
    absolute, and clearing actually clears.
    """

    def setUp(self) -> None:
        cache.clear()
        self.client = APIClient()
        self.user = create_user(username="baker")
        self.url = reverse("users:profile_update")

    def test_cover_is_absent_until_one_is_uploaded(self) -> None:
        self.client.force_login(self.user)

        response = self.client.get(reverse("users:profile"))

        self.assertIsNone(response.json()["cover_url"])

    def test_owner_can_upload_a_cover(self) -> None:
        self.client.force_login(self.user)

        response = self.client.patch(
            self.url, {"cover": make_image_file()}, format="multipart"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        cover_url = response.json()["cover_url"]
        self.assertIsNotNone(cover_url)
        # Absolute, because the frontend is a different origin.
        self.assertTrue(cover_url.startswith("http"))
        self.assertIn("/covers/", cover_url)

    def test_uploaded_cover_does_not_keep_the_client_filename(self) -> None:
        # The client name is used only for its extension; interpolating it
        # into a storage path is how traversal and collision bugs start.
        self.client.force_login(self.user)

        self.client.patch(
            self.url,
            {"cover": make_image_file(name="../../etc/passwd.png")},
            format="multipart",
        )

        self.user.profile.refresh_from_db()
        self.assertNotIn("passwd", self.user.profile.cover.name)
        self.assertTrue(self.user.profile.cover.name.endswith(".png"))

    def test_a_non_image_payload_is_rejected(self) -> None:
        self.client.force_login(self.user)
        fake = SimpleUploadedFile("evil.png", b"not-an-image", content_type="image/png")

        response = self.client.patch(self.url, {"cover": fake}, format="multipart")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.user.profile.refresh_from_db()
        self.assertFalse(self.user.profile.cover)

    def test_an_svg_is_rejected(self) -> None:
        # SVG can carry script; storing one would be stored XSS. A `.png`
        # extension does not launder it — the bytes are what is checked.
        self.client.force_login(self.user)
        svg = SimpleUploadedFile(
            "evil.png", b"<svg xmlns='http://www.w3.org/2000/svg'/>",
            content_type="image/png",
        )

        response = self.client.patch(self.url, {"cover": svg}, format="multipart")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.user.profile.refresh_from_db()
        self.assertFalse(self.user.profile.cover)

    def test_an_oversized_cover_is_rejected_for_being_oversized(self) -> None:
        # A *decodable* image over the cap, so this exercises the size rule
        # rather than the corrupt-image rule that guards the tests above.
        self.client.force_login(self.user)
        oversized = make_image_file(name="big.png", size=(1400, 1400), compress=False)
        self.assertGreater(oversized.size, COVER_MAX_SIZE_BYTES)

        response = self.client.patch(self.url, {"cover": oversized}, format="multipart")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # The domain rule's own message, not the generic "not a valid image"
        # that a corrupt file would produce — proof the size branch ran.
        self.assertIn(
            "Cover image must be smaller than 4 MB.",
            response.json()["error"]["details"]["non_field_errors"],
        )
        self.user.profile.refresh_from_db()
        self.assertFalse(self.user.profile.cover)

    def test_explicit_null_removes_the_cover(self) -> None:
        self.client.force_login(self.user)
        self.client.patch(self.url, {"cover": make_image_file()}, format="multipart")

        response = self.client.patch(self.url, {"cover": None}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.json()["cover_url"])
        self.user.profile.refresh_from_db()
        self.assertFalse(self.user.profile.cover)

    def test_updating_another_field_leaves_the_cover_alone(self) -> None:
        # A PATCH that never mentions the cover must not clobber it.
        self.client.force_login(self.user)
        self.client.patch(self.url, {"cover": make_image_file()}, format="multipart")
        before = self.client.get(reverse("users:profile")).json()["cover_url"]

        self.client.patch(self.url, {"display_name": "คุณเบเกอร์"}, format="json")

        after = self.client.get(reverse("users:profile")).json()["cover_url"]
        self.assertEqual(before, after)

    def test_cover_upload_requires_authentication(self) -> None:
        response = self.client.patch(
            self.url, {"cover": make_image_file()}, format="multipart"
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_the_cover_never_reaches_the_public_profile_payload(self) -> None:
        # Scoping is deliberate: no public consumer exists, so no public
        # surface. If a public profile page ships, this test is the reminder.
        self.client.force_login(self.user)
        self.client.patch(self.url, {"cover": make_image_file()}, format="multipart")
        self.client.logout()

        response = self.client.get(
            reverse("users:public_profile", kwargs={"username": "baker"})
        )

        self.assertNotIn("cover_url", response.json())
