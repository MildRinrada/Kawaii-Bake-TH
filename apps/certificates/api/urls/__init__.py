"""Public certificate routes, mounted at ``/api/v1/certificates/``.

Only the verification endpoint lives here  the single anonymous read,
keyed by UUID so certificate records cannot be enumerated.
"""

from __future__ import annotations

from django.urls import path

from apps.certificates.api.views.certificate_views import CertificateVerifyView

app_name = "certificates"

urlpatterns = [
    path(
        "<uuid:verification_token>/",
        CertificateVerifyView.as_view(),
        name="verify",
    ),
]
