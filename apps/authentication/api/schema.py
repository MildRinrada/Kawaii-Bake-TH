"""OpenAPI schema extensions.

Imported from ``AuthenticationConfig.ready`` so drf-spectacular can discover
the extension before it walks the URL conf.
"""

from __future__ import annotations

from typing import Any

from django.conf import settings
from drf_spectacular.extensions import OpenApiAuthenticationExtension


class CookieSessionAuthScheme(OpenApiAuthenticationExtension):
    """Document cookie-session auth in the generated schema.

    Without this, drf-spectacular cannot resolve the custom authentication
    class and silently omits security requirements  which would tell the
    Next.js client that protected endpoints are public.
    """

    target_class = (
        "apps.authentication.api.authentication.CsrfEnforcedSessionAuthentication"
    )
    name = "cookieAuth"

    def get_security_definition(self, auto_schema: Any) -> dict[str, str]:
        """Describe the session cookie as an API key carried in a cookie."""
        return {
            "type": "apiKey",
            "in": "cookie",
            "name": settings.SESSION_COOKIE_NAME,
        }
