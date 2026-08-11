"""Legal routes, mounted at ``/api/v1/legal/`` by config."""

from __future__ import annotations

from django.urls import path

from apps.legal.api.views import LegalDocumentDetailView, LegalDocumentListView

app_name = "legal"

urlpatterns = [
    path("", LegalDocumentListView.as_view(), name="list"),
    path("<slug:kind>/", LegalDocumentDetailView.as_view(), name="detail"),
]
