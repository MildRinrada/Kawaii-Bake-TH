"""The course visibility matrix — the enforcement mechanism for permissions."""

from __future__ import annotations

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.courses.constants import (
    CourseScope,
    CourseStatus,
    CourseVisibility,
    EnrollmentStatus,
)
from apps.courses.tests.factories import create_course, enroll_user
from apps.users.tests.factories import create_user

STATUSES = (CourseStatus.DRAFT, CourseStatus.PUBLISHED, CourseStatus.ARCHIVED)
VISIBILITIES = (
    CourseVisibility.PUBLIC,
    CourseVisibility.UNLISTED,
    CourseVisibility.PRIVATE,
)

STRANGER_CAN_OPEN = {
    (CourseStatus.PUBLISHED, CourseVisibility.PUBLIC),
    (CourseStatus.PUBLISHED, CourseVisibility.UNLISTED),
}
APPEARS_IN_PUBLIC_LIST = {(CourseStatus.PUBLISHED, CourseVisibility.PUBLIC)}


class CourseVisibilityMatrixTests(TestCase):
    """Every status × visibility × viewer combination, both endpoints."""

    @classmethod
    def setUpTestData(cls) -> None:
        cls.instructor = create_user(username="teacher")
        cls.stranger = create_user(username="stranger")
        cls.staff = create_user(username="staffer", is_staff=True)

        cls.courses = {}
        for status in STATUSES:
            for visibility in VISIBILITIES:
                cls.courses[(status, visibility)] = create_course(
                    instructor=cls.instructor,
                    slug=f"{status}-{visibility}",
                    status=status,
                    visibility=visibility,
                )

    def _detail_status(self, *, slug: str, user=None) -> int:
        client = APIClient()
        if user is not None:
            client.force_login(user)
        return client.get(reverse("courses:detail", kwargs={"slug": slug})).status_code

    def _list_slugs(self, *, user=None, scope: str | None = None) -> set[str]:
        client = APIClient()
        if user is not None:
            client.force_login(user)
        params = {"scope": scope} if scope else {}
        response = client.get(reverse("courses:list"), params)
        self.assertEqual(response.status_code, 200)
        return {item["slug"] for item in response.json()["results"]}

    def test_anonymous_detail_access(self) -> None:
        for key, course in self.courses.items():
            with self.subTest(state=key):
                expected = 200 if key in STRANGER_CAN_OPEN else 404
                self.assertEqual(self._detail_status(slug=course.slug), expected)

    def test_stranger_detail_access(self) -> None:
        for key, course in self.courses.items():
            with self.subTest(state=key):
                expected = 200 if key in STRANGER_CAN_OPEN else 404
                self.assertEqual(
                    self._detail_status(slug=course.slug, user=self.stranger), expected
                )

    def test_instructor_can_always_open_own_course(self) -> None:
        for key, course in self.courses.items():
            with self.subTest(state=key):
                self.assertEqual(
                    self._detail_status(slug=course.slug, user=self.instructor), 200
                )

    def test_staff_can_always_open_any_course(self) -> None:
        for key, course in self.courses.items():
            with self.subTest(state=key):
                self.assertEqual(
                    self._detail_status(slug=course.slug, user=self.staff), 200
                )

    def test_public_list_shows_only_published_public(self) -> None:
        for viewer in (None, self.stranger):
            visible = self._list_slugs(user=viewer)
            for key, course in self.courses.items():
                with self.subTest(state=key, viewer=viewer):
                    if key in APPEARS_IN_PUBLIC_LIST:
                        self.assertIn(course.slug, visible)
                    else:
                        self.assertNotIn(course.slug, visible)

    def test_scope_mine_shows_every_own_course(self) -> None:
        visible = self._list_slugs(user=self.instructor, scope=CourseScope.MINE)

        for key, course in self.courses.items():
            with self.subTest(state=key):
                self.assertIn(course.slug, visible)

    def test_scope_mine_never_leaks_another_instructor(self) -> None:
        create_course(instructor=self.stranger, slug="strangers-draft")

        visible = self._list_slugs(user=self.instructor, scope=CourseScope.MINE)

        self.assertNotIn("strangers-draft", visible)

    def test_scope_mine_requires_authentication(self) -> None:
        response = APIClient().get(reverse("courses:list"), {"scope": CourseScope.MINE})

        self.assertEqual(response.status_code, 401)

    def test_scope_all_is_narrowed_for_non_staff(self) -> None:
        visible = self._list_slugs(user=self.stranger, scope=CourseScope.ALL)

        for key, course in self.courses.items():
            if key not in APPEARS_IN_PUBLIC_LIST:
                self.assertNotIn(course.slug, visible)

    def test_scope_all_shows_everything_to_staff(self) -> None:
        visible = self._list_slugs(user=self.staff, scope=CourseScope.ALL)

        for key, course in self.courses.items():
            with self.subTest(state=key):
                self.assertIn(course.slug, visible)

    def test_unlisted_is_reachable_but_undiscoverable(self) -> None:
        course = self.courses[(CourseStatus.PUBLISHED, CourseVisibility.UNLISTED)]

        self.assertEqual(self._detail_status(slug=course.slug), 200)
        self.assertNotIn(course.slug, self._list_slugs())

    def test_archived_course_stays_readable_to_enrolled_student(self) -> None:
        # The one branch recipes' visibility does not have: a student's
        # progress must not vanish because the instructor tidied up.
        course = self.courses[(CourseStatus.ARCHIVED, CourseVisibility.PUBLIC)]
        student = create_user(username="student")
        enroll_user(user=student, course=course, status=EnrollmentStatus.ACTIVE)

        self.assertEqual(self._detail_status(slug=course.slug, user=student), 200)
        # But a draft stays hidden even from the enrolled student.
        draft = self.courses[(CourseStatus.DRAFT, CourseVisibility.PUBLIC)]
        enroll_user(user=student, course=draft, status=EnrollmentStatus.ACTIVE)
        self.assertEqual(self._detail_status(slug=draft.slug, user=student), 404)

    def test_dropped_student_loses_archived_access(self) -> None:
        course = self.courses[(CourseStatus.ARCHIVED, CourseVisibility.UNLISTED)]
        student = create_user(username="dropout")
        enroll_user(user=student, course=course, status=EnrollmentStatus.DROPPED)

        self.assertEqual(self._detail_status(slug=course.slug, user=student), 404)

    def test_hidden_course_returns_404_not_403(self) -> None:
        course = self.courses[(CourseStatus.PUBLISHED, CourseVisibility.PRIVATE)]
        client = APIClient()
        client.force_login(self.stranger)

        response = client.get(reverse("courses:detail", kwargs={"slug": course.slug}))

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "not_found")
