"""Staff account-action routes, mounted at ``/api/v1/admin/users/``.

Shares the prefix with the roster (``apps.users.api.urls.admin``) -
Django falls through to this include for paths the roster does not
declare. The ``admin/`` prefix is a naming convention, not the
permission: every view declares ``IsAdminUser`` itself.
"""

from __future__ import annotations

from django.urls import path

from apps.authentication.api.views.staff_account_views import (
    AdminCreateUserView,
    AdminResendVerificationView,
    AdminSendPasswordResetView,
)

app_name = "auth_admin_accounts"

urlpatterns = [
    path("create/", AdminCreateUserView.as_view(), name="create"),
    path(
        "<int:user_id>/send-password-reset/",
        AdminSendPasswordResetView.as_view(),
        name="send-password-reset",
    ),
    path(
        "<int:user_id>/resend-verification/",
        AdminResendVerificationView.as_view(),
        name="resend-verification",
    ),
]
