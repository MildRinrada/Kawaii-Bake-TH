"""Email seam.

Business logic depends on :class:`EmailSender` and never on a vendor SDK or on
``django.core.mail`` directly.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class TemplatedEmail:
    """An email described by a template rather than a rendered body.

    Attributes:
        subject: Subject line.
        recipients: Destination addresses.
        template_name: Template base path, without extension. The sender renders
            ``<template_name>.txt`` and, when present, ``<template_name>.html``.
        context: Template rendering context.
    """

    subject: str
    recipients: Sequence[str]
    template_name: str
    context: Mapping[str, Any]


class EmailSender(Protocol):
    """Sends templated email."""

    def send(self, message: TemplatedEmail) -> None:
        """Render and deliver ``message``."""
        ...
