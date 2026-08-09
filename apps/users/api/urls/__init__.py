"""Users API routes, mounted at ``/api/v1/users/``.

Literal paths are declared before the ``<slug:username>`` catch-all so a handle
can never shadow an endpoint. The same names are also in
``constants.RESERVED_USERNAMES`` as a second line of defence.
"""

from __future__ import annotations

from django.urls import path

from apps.users.api.views.account_views import AccountDeactivateView
from apps.users.api.views.preference_views import PreferenceView
from apps.users.api.views.profile_views import (
    ProfileDetailView,
    ProfileUpdateView,
    PublicProfileView,
)

app_name = "users"

urlpatterns = [
    path("profile/", ProfileDetailView.as_view(), name="profile"),
    path("profile/update/", ProfileUpdateView.as_view(), name="profile_update"),
    path("preferences/", PreferenceView.as_view(), name="preferences"),
    path("account/deactivate/", AccountDeactivateView.as_view(), name="account_deactivate"),
    path("<slug:username>/", PublicProfileView.as_view(), name="public_profile"),
]
