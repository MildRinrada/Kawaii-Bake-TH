"""Email sender backed by Django's configured mail backend."""

from __future__ import annotations

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template import TemplateDoesNotExist
from django.template.loader import render_to_string

from infrastructure.email.base import TemplatedEmail


class DjangoEmailSender:
    """Render templates and deliver through ``django.core.mail``.

    The transport itself (SMTP, console, in-memory) is chosen by the
    ``EMAIL_BACKEND`` setting, so this one adapter serves every environment.
    """

    def send(self, message: TemplatedEmail) -> None:
        """Render ``message`` and hand it to the configured mail backend.

        Args:
            message: The templated email to deliver.
        """
        context = dict(message.context)
        body = render_to_string(f"{message.template_name}.txt", context)

        email = EmailMultiAlternatives(
            subject=message.subject,
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=list(message.recipients),
        )

        try:
            html_body = render_to_string(f"{message.template_name}.html", context)
        except TemplateDoesNotExist:
            html_body = None
        if html_body:
            email.attach_alternative(html_body, "text/html")

        email.send(fail_silently=False)
