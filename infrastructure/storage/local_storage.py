"""Local filesystem storage for user media (development and single-host deploys)."""

from __future__ import annotations

from django.core.files.storage import FileSystemStorage


class LocalMediaStorage(FileSystemStorage):
    """Filesystem storage that never overwrites an existing file.

    ``FileSystemStorage`` already appends a random suffix on collision; this
    subclass exists so the backend is named explicitly in ``settings.STORAGES``
    and can be swapped for ``S3MediaStorage`` without touching model code.
    """

    def get_available_name(self, name: str, max_length: int | None = None) -> str:
        """Return a free filename, never clobbering an existing upload."""
        return super().get_available_name(name, max_length=max_length)
