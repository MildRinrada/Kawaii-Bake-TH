"""File path helpers shared by every app that stores uploads."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4


def build_upload_path(*, directory: str, filename: str) -> str:
    """Build a randomised storage path for an uploaded file.

    The client-supplied filename is used only for its extension; interpolating
    it into a storage path invites traversal and collision bugs.

    Args:
        directory: Destination directory beneath the media root.
        filename: The client-supplied filename.

    Returns:
        A randomised path.
    """
    extension = Path(filename or "").suffix.lower()
    return f"{directory}/{uuid4().hex}{extension}"
