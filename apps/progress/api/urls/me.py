"""The progress overview, mounted at ``/api/v1/me/`` by config."""

from __future__ import annotations

from django.urls import path

from apps.progress.api.views.progress_views import MyProgressView

app_name = "my_progress"

urlpatterns = [
    path("progress/", MyProgressView.as_view(), name="overview"),
]
