"""Console email delivery.

Intentionally empty. Django already ships a console transport, selected with
``EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"`` in
``config/settings/development.py``. :class:`~infrastructure.email.smtp_email.DjangoEmailSender`
delegates to whichever backend is configured, so a second adapter here would
duplicate Django rather than abstract it.
"""

from __future__ import annotations
