"""Authentication API routes, mounted at ``/api/v1/auth/``."""

from __future__ import annotations

from django.urls import path

from apps.authentication.api.views.password_views import (
    PasswordChangeView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
)
from apps.authentication.api.views.session_views import (
    CsrfView,
    LoginView,
    LogoutView,
    MeView,
    RegistrationView,
    UsernameAvailabilityView,
)
from apps.authentication.api.views.verification_views import (
    EmailVerificationConfirmView,
    EmailVerificationResendView,
)

app_name = "authentication"

urlpatterns = [
    path("csrf/", CsrfView.as_view(), name="csrf"),
    path("register/", RegistrationView.as_view(), name="register"),
    path(
        "username-available/",
        UsernameAvailabilityView.as_view(),
        name="username_available",
    ),
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("me/", MeView.as_view(), name="me"),
    path(
        "password-reset/",
        PasswordResetRequestView.as_view(),
        name="password_reset",
    ),
    path(
        "password-reset/confirm/",
        PasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path("password-change/", PasswordChangeView.as_view(), name="password_change"),
    path(
        "verify-email/",
        EmailVerificationConfirmView.as_view(),
        name="verify_email",
    ),
    path(
        "verify-email/resend/",
        EmailVerificationResendView.as_view(),
        name="verify_email_resend",
    ),
    # Reserved for the JWT phase; see api/credentials/jwt_issuer.py.
    # path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
]
