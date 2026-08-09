"""Intentionally empty.

Creating a user's ``Profile`` and ``UserPreference`` is business logic, and the
coding guidelines keep business logic out of signal receivers. It lives in
``UserManager._create_user`` instead, inside one ``transaction.atomic()``.

That placement is not merely stylistic:

* ``post_save`` fires on **every** save, including
  ``save(update_fields=["last_login"])``, ``loaddata`` and data migrations, so a
  receiver needs ``created`` and ``raw`` guards to behave.
* A failing receiver surfaces as an opaque error from ``.save()`` rather than
  from the operation that actually failed.
* The manager is the true choke point: ``createsuperuser``, the admin and test
  factories all pass through it, whereas a registration-service call would not.

``apps.users.repositories.user_repository.ensure_related_records`` provides an
idempotent reconciliation path for rows created outside the manager.
"""

from __future__ import annotations
