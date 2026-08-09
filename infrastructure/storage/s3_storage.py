"""S3-compatible object storage.

Not implemented in Phase 1. When object storage is needed:

1. Add ``django-storages[s3]`` to ``requirements/production.txt``.
2. Define ``S3MediaStorage`` here as a ``S3Boto3Storage`` subclass.
3. Point the ``avatars`` alias in ``settings.STORAGES`` at it.

No model change and no migration are required, because model fields resolve
their backend through ``infrastructure.storage.get_media_storage``.
"""

from __future__ import annotations
