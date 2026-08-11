"""Staff review routes, mounted at ``/api/v1/admin/reviews/``.

The ``admin/`` prefix is a naming convention, not the permission: the
view declares ``IsAdminUser`` itself, so a future re-mount cannot
accidentally expose it.
"""

from __future__ import annotations

from django.urls import path

from apps.reviews.api.views.admin_views import AdminReviewListView

app_name = "reviews_admin"

urlpatterns = [
    path("", AdminReviewListView.as_view(), name="list"),
]
