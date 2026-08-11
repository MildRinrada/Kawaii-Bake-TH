"""Enumerations and limits for the legal-documents app."""

from __future__ import annotations

from django.db import models


class LegalDocumentKind(models.TextChoices):
    """The documents the platform publishes and a user consents to.

    A closed set on purpose: consent language, routing and the public
    page all reference these slugs, so "add a document" is a deliberate
    code change, never a typo'd row.
    """

    TERMS = "terms", "Terms of service"
    PRIVACY = "privacy", "Privacy policy"
    PDPA = "pdpa", "PDPA notice"
    COOKIE = "cookie", "Cookie policy"


TITLE_MAX_LENGTH = 120
