"""The authentication app deliberately defines **no models**.

Account data lives in ``apps.users``. The two flows that would normally need
their own tables  email verification and password reset  use stateless,
signed tokens instead:

* Tokens are HMACs over user state, keyed by ``SECRET_KEY``. They self-invalidate
  when the state they hash changes, so there is nothing to store or clean up.
* See ``apps/authentication/tokens/`` and ``docs/adr/0006-stateless-auth-tokens.md``.

Sessions are stored by ``django.contrib.sessions``, which owns its own table.

If OAuth or social login is added later it *will* need a provider-link table;
that is a deliberate, documented exception rather than an oversight.
"""

from __future__ import annotations
