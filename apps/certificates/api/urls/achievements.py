"""The badge catalogue, mounted at ``/api/v1/achievements/``.

Deliberately separate from ``/api/v1/me/achievements/``: this route says
what there *is* to earn, that one says what the caller *has* earned. The
split keeps the badge definition (system-owned presentation) apart from
the achievement fact (per-user, append-only) — see ADR 0024.
"""

from __future__ import annotations

from django.urls import path

from apps.certificates.api.views.certificate_views import BadgeCatalogView

app_name = "achievement_catalog"

urlpatterns = [
    path("", BadgeCatalogView.as_view(), name="badges"),
]
