"""Recipe API routes, mounted at ``/api/v1/recipes/``.

Two ordering rules matter here:

* Literal routes are declared **before** ``<str:slug>``, so a recipe can never
  shadow an endpoint. ``constants.RESERVED_RECIPE_SLUGS`` is the second line of
  defence.
* The converter is ``<str:slug>``, not ``<slug:slug>``. Django's ``slug``
  converter matches ``[-a-zA-Z0-9_]+``, which rejects every Thai slug and would
  produce a 404 that looks like a permissions bug.
"""

from __future__ import annotations

from django.urls import path

from apps.recipes.api.views.image_views import (
    RecipeImageCreateView,
    RecipeImageDeleteView,
)
from apps.recipes.api.views.publish_views import (
    RecipeArchiveView,
    RecipePublishView,
    RecipeUnpublishView,
)
from apps.recipes.api.views.recipe_views import RecipeDetailView, RecipeListCreateView
from apps.recipes.api.views.search_views import RecipeSearchView

app_name = "recipes"

urlpatterns = [
    path("", RecipeListCreateView.as_view(), name="list"),
    path("search/", RecipeSearchView.as_view(), name="search"),
    path("<str:slug>/", RecipeDetailView.as_view(), name="detail"),
    path("<str:slug>/publish/", RecipePublishView.as_view(), name="publish"),
    path("<str:slug>/unpublish/", RecipeUnpublishView.as_view(), name="unpublish"),
    path("<str:slug>/archive/", RecipeArchiveView.as_view(), name="archive"),
    path("<str:slug>/images/", RecipeImageCreateView.as_view(), name="image_create"),
    path(
        "<str:slug>/images/<int:image_id>/",
        RecipeImageDeleteView.as_view(),
        name="image_delete",
    ),
]
