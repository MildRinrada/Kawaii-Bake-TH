"""Course API routes, mounted at ``/api/v1/courses/``.

The lessons app mounts two additional routes under the same prefix
(``{slug}/lessons/…`` and ``{slug}/progress/``) from its own urlconf  the
shared prefix is a config concern, not app coupling.

Literals are declared before ``<str:slug>`` (which also would not match a
path containing ``/``), and every literal is in ``RESERVED_COURSE_SLUGS``.
"""

from __future__ import annotations

from django.urls import path

from apps.courses.api.views.course_views import CourseDetailView, CourseListCreateView
from apps.courses.api.views.lifecycle_views import (
    CourseArchiveView,
    CoursePublishView,
    CourseUnpublishView,
    EnrollView,
    UnenrollView,
)

app_name = "courses"

urlpatterns = [
    path("", CourseListCreateView.as_view(), name="list"),
    path("<str:slug>/", CourseDetailView.as_view(), name="detail"),
    path("<str:slug>/publish/", CoursePublishView.as_view(), name="publish"),
    path("<str:slug>/unpublish/", CourseUnpublishView.as_view(), name="unpublish"),
    path("<str:slug>/archive/", CourseArchiveView.as_view(), name="archive"),
    path("<str:slug>/enroll/", EnrollView.as_view(), name="enroll"),
    path("<str:slug>/unenroll/", UnenrollView.as_view(), name="unenroll"),
]
