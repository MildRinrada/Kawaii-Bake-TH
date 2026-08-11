"""Certificate routes nested under ``/api/v1/courses/``  mounted by config.

The shared prefix is a config concern, not app coupling (ADR 0009); the
two-segment pattern cannot collide with courses' own routes.
"""

from __future__ import annotations

from django.urls import path

from apps.certificates.api.views.certificate_views import CourseCertificateView

app_name = "course_certificates"

urlpatterns = [
    path(
        "<str:slug>/certificate/",
        CourseCertificateView.as_view(),
        name="issue",
    ),
]
