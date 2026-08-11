"""Background delivery of authentication emails.

Tokens are minted **inside** the task rather than passed in, so no credential
is ever written to the broker.
"""

from __future__ import annotations

from celery import shared_task
from django.conf import settings

from apps.authentication.constants import (
    SUBJECT_PASSWORD_CHANGED,
    SUBJECT_PASSWORD_RESET,
    SUBJECT_VERIFY_EMAIL,
)
from apps.authentication.tokens.email_verification_token import email_verification_token
from apps.authentication.tokens.password_reset_token import password_reset_token
from apps.authentication.utils import build_frontend_url, encode_uid
from apps.users.selectors import user_selector
from infrastructure.email import TemplatedEmail, get_email_sender


def _base_context() -> dict[str, str]:
    """Return context every auth email needs.

    Emails render without a request (and often from a Celery worker), so
    context processors never run  site values are passed explicitly.
    """
    return {
        "site_name": settings.SITE_NAME,
        "frontend_url": str(settings.FRONTEND_BASE_URL).rstrip("/"),
    }


@shared_task(name="authentication.send_verification_email")
def send_verification_email_task(user_id: int) -> None:
    """Send an email-confirmation link.

    Args:
        user_id: Primary key of the recipient.
    """
    user = user_selector.get_by_id(user_id=user_id)
    if user is None or user.is_email_verified:
        return

    link = build_frontend_url(
        path=settings.FRONTEND_EMAIL_VERIFY_PATH,
        uidb64=encode_uid(user.pk),
        token=email_verification_token.make_token(user),
    )
    get_email_sender().send(
        TemplatedEmail(
            subject=SUBJECT_VERIFY_EMAIL,
            recipients=[user.email],
            template_name="authentication/emails/verify_email",
            context={
                **_base_context(),
                "username": user.username,
                "verification_url": link,
                "expiry_hours": settings.EMAIL_VERIFICATION_TIMEOUT // 3600,
            },
        )
    )


@shared_task(name="authentication.send_password_reset_email")
def send_password_reset_email_task(user_id: int) -> None:
    """Send a password-reset link.

    Args:
        user_id: Primary key of the recipient.
    """
    user = user_selector.get_by_id(user_id=user_id)
    if user is None:
        return

    link = build_frontend_url(
        path=settings.FRONTEND_PASSWORD_RESET_PATH,
        uidb64=encode_uid(user.pk),
        token=password_reset_token.make_token(user),
    )
    get_email_sender().send(
        TemplatedEmail(
            subject=SUBJECT_PASSWORD_RESET,
            recipients=[user.email],
            template_name="authentication/emails/password_reset",
            context={
                **_base_context(),
                "username": user.username,
                "reset_url": link,
                "expiry_minutes": settings.PASSWORD_RESET_TIMEOUT // 60,
            },
        )
    )


@shared_task(name="authentication.send_password_changed_email")
def send_password_changed_email_task(user_id: int) -> None:
    """Notify a user that their password changed.

    This is a security notification, not a courtesy: it is how a victim learns
    that someone else changed their password.

    Args:
        user_id: Primary key of the recipient.
    """
    user = user_selector.get_by_id(user_id=user_id)
    if user is None:
        return

    get_email_sender().send(
        TemplatedEmail(
            subject=SUBJECT_PASSWORD_CHANGED,
            recipients=[user.email],
            template_name="authentication/emails/password_changed",
            context={**_base_context(), "username": user.username},
        )
    )
