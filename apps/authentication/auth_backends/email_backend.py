"""Email-based authentication backend."""

from __future__ import annotations

from django.contrib.auth.backends import ModelBackend


class EmailBackend(ModelBackend):
    """Authenticate against the email address instead of a username.

    ``UserManager.get_by_natural_key`` already resolves emails
    case-insensitively, so this class only needs to exist as the named,
    stable backend path referenced by ``settings.AUTHENTICATION_BACKENDS`` and
    by every ``login()`` call.

    Two behaviours are inherited on purpose and must not be overridden:

    * ``user_can_authenticate`` keeps rejecting inactive users. It is also
      called from ``get_user`` on **every** session restore, so leaving it
      strict is what makes deactivation invalidate live sessions immediately.
    * ``get_user`` performs no extra state checks, keeping session restoration
      to a single indexed lookup.

    The API sign-in path does not call ``authenticate()`` at all — the login
    service verifies credentials itself so it can distinguish "wrong password"
    from "deactivated" from "unverified", which ``authenticate()`` collapses
    into ``None``. This backend still serves Django admin sign-in and every
    session restore.
    """
