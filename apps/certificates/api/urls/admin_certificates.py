"""Staff certificate routes, mounted at ``/api/v1/admin/certificates/``.

Separate from ``admin.py`` (the achievements surface at
``/api/v1/admin/achievements/``) because config mounts them under
different prefixes. The ``admin/`` prefix is a naming convention, not
the permission: every view here declares ``IsAdminUser`` itself, so a
future re-mount cannot accidentally expose them.
"""

from __future__ import annotations

from django.urls import path

from apps.certificates.api.views.admin_views import (
    AdminCertificateListView,
    AdminCertificateRevokeView,
    AdminTemplateDetailView,
    AdminTemplateListView,
    AdminTemplatePublishView,
    AdminTemplateResetView,
)

app_name = "certificates_admin"

urlpatterns = [
    path("", AdminCertificateListView.as_view(), name="list"),
    # The designer surface (ADR 0029). Literal segments route before the
    # integer certificate pattern below by shape, not order.
    path("templates/", AdminTemplateListView.as_view(), name="templates"),
    path(
        "templates/<str:course_slug>/",
        AdminTemplateDetailView.as_view(),
        name="template-detail",
    ),
    path(
        "templates/<str:course_slug>/publish/",
        AdminTemplatePublishView.as_view(),
        name="template-publish",
    ),
    path(
        "templates/<str:course_slug>/reset/",
        AdminTemplateResetView.as_view(),
        name="template-reset",
    ),
    path(
        "<int:certificate_id>/revoke/",
        AdminCertificateRevokeView.as_view(),
        name="revoke",
    ),
]
