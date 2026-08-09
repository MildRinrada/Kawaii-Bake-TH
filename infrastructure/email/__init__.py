"""Email infrastructure — public API."""

from __future__ import annotations

from infrastructure.email.base import EmailSender, TemplatedEmail
from infrastructure.email.smtp_email import DjangoEmailSender


def get_email_sender() -> EmailSender:
    """Return the configured email sender.

    Returns:
        An :class:`EmailSender` implementation.
    """
    return DjangoEmailSender()


__all__ = ["EmailSender", "TemplatedEmail", "DjangoEmailSender", "get_email_sender"]
