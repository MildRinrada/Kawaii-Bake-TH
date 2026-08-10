"""Public security routes, mounted at ``/api/v1/security/`` by config.

Two endpoints, both anonymous-safe: the guard policy and the signal
ingest. Everything an operator uses lives under the staff prefix in
``admin.py`` instead.
"""

from __future__ import annotations

from django.urls import path

from apps.security.api.views.public_views import (
    ClientPolicyView,
    ClientSignalView,
    EdgeSignalView,
)

app_name = "security"

urlpatterns = [
    path("client-policy/", ClientPolicyView.as_view(), name="client-policy"),
    path("client-signals/", ClientSignalView.as_view(), name="client-signals"),
    path("edge-signals/", EdgeSignalView.as_view(), name="edge-signals"),
]
