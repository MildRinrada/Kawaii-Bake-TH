"""OAuth / social sign-in.

Not implemented in Phase 1. The seams that make it additive already exist:

* ``api/credentials/`` is the only place a session is established, and it names
  its backend explicitly  so a second backend can be appended to
  ``AUTHENTICATION_BACKENDS`` without touching any view.
* Accounts without a local password use ``set_unusable_password()``;
  ``user_selector.get_for_password_reset`` already excludes them, so a
  social-only account will never be sent reset mail.

What this flow *will* need, and cannot avoid, is a provider-link table
(``provider``, ``provider_uid``, user FK). That is a deliberate exception to
the Phase 1 "no unnecessary tables" rule and is recorded in
``docs/adr/0007-session-auth-for-phase-1.md``.
"""

from __future__ import annotations
