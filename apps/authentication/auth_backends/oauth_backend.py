"""OAuth / social authentication backend.

Not implemented in Phase 1. When it lands:

1. Add a provider-link table (``provider``, ``provider_uid``, user FK). This is
   the one place the "no unnecessary tables" rule genuinely cannot hold — see
   ``docs/adr/0007-session-auth-for-phase-1.md``.
2. Define ``OAuthBackend`` here and append it to
   ``settings.AUTHENTICATION_BACKENDS``.
3. Nothing else changes: ``session_issuer`` already passes ``backend=``
   explicitly to ``login()``, which is exactly what breaks when a second
   backend is added to a project that relied on the implicit single-backend
   case.

Accounts created through OAuth get ``set_unusable_password()``; the password
reset selector already filters those out.
"""

from __future__ import annotations
