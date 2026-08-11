"""Staff category routes, mounted at ``/api/v1/admin/recipe-categories/``.

The ``admin/`` prefix is a naming convention, not the permission: every
view here declares ``IsAdminUser`` itself, so a future re-mount cannot
accidentally expose them.
"""

from __future__ import annotations

from django.urls import path

from apps.recipe_categories.api.views.admin_views import (
    AdminCategoryDetailView,
    AdminCategoryListView,
)

app_name = "recipe_categories_admin"

urlpatterns = [
    path("", AdminCategoryListView.as_view(), name="list"),
    path(
        "<int:category_id>/",
        AdminCategoryDetailView.as_view(),
        name="detail",
    ),
]
