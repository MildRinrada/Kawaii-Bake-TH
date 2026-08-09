"""Storage seam.

Django's ``Storage`` class is already the right abstraction, so this package
does not invent a parallel one. It only decides *which* storage backend a model
field should use, and exposes that decision as a callable.

Passing a callable (rather than a storage instance) to a ``FileField`` means
Django records the reference in the migration instead of the concrete backend,
so switching local disk for S3 later requires no migration.
"""

from __future__ import annotations

from django.conf import settings
from django.core.files.storage import Storage, storages


def get_media_storage() -> Storage:
    """Return the storage backend configured for user media uploads.

    Resolved from ``settings.STORAGES`` using the ``MEDIA_STORAGE_ALIAS`` alias,
    falling back to the default backend when that alias is not configured.

    Returns:
        The configured storage backend instance.
    """
    alias = getattr(settings, "MEDIA_STORAGE_ALIAS", "default")
    if alias not in settings.STORAGES:
        alias = "default"
    return storages[alias]
