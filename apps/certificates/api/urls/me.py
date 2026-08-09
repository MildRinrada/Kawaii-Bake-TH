"""The caller's certificates and achievements, mounted at ``/api/v1/me/``.

Shares the ``me/`` prefix with progress and assistant by config (ADR 0009);
the patterns cannot collide.
"""

from __future__ import annotations

from django.urls import path

from apps.certificates.api.views.certificate_views import (
    MyAchievementsView,
    MyCertificatesView,
)

app_name = "my_certificates"

urlpatterns = [
    path("certificates/", MyCertificatesView.as_view(), name="certificates"),
    path("achievements/", MyAchievementsView.as_view(), name="achievements"),
]
