"""Intentionally empty.

Authentication side effects — sending verification mail, stamping ``last_login``,
resetting rate-limit counters — are explicit calls inside the services that own
them. Implicit cross-app signal chains become undebuggable at scale, and the
architecture requires cross-app work to go through a published service API.

Signals remain acceptable for genuinely decoupled concerns such as cache
invalidation or audit logging; none of those exist in Phase 1.
"""

from __future__ import annotations
