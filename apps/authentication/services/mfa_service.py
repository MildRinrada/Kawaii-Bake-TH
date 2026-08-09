"""Two-factor authentication.

Not implemented in Phase 1. The whole of 2FA slots into a single gap in the
login flow: instead of calling ``issuer.issue()`` immediately, stash
``{"pending_user_id": ...}`` in the session and return
``{"status": "mfa_required"}``; call ``issue()`` only once the challenge
passes.

That envelope already ships — :class:`~apps.authentication.api.credentials.base.IssuedCredential`
carries a ``status`` field and ``constants.STATUS_MFA_REQUIRED`` is defined —
so adding 2FA later is additive rather than a breaking response-shape change.
Because ``issue()`` has exactly one call site, the insertion touches one line.

Storage needs no new table either: a ``totp_secret`` column plus hashed
recovery codes on ``users.User`` suffice. Nothing is added now.
"""

from __future__ import annotations
