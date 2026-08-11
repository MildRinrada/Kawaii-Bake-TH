"""Credential issuance - public API."""

from __future__ import annotations

from django.conf import settings
from django.utils.module_loading import import_string

from apps.authentication.api.credentials.base import CredentialIssuer, IssuedCredential


def get_credential_issuer() -> CredentialIssuer:
    """Return the configured credential issuer.

    Views must always resolve the issuer through this function rather than
    importing a concrete class, otherwise the seam stops being a seam.

    Returns:
        The issuer named by ``settings.AUTH_CREDENTIAL_ISSUER``.
    """
    return import_string(settings.AUTH_CREDENTIAL_ISSUER)()


__all__ = ["CredentialIssuer", "IssuedCredential", "get_credential_issuer"]
