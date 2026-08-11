"""Users models  public API.

Phase 1 defines exactly three tables: ``User``, ``Profile`` and
``UserPreference``.
"""

from __future__ import annotations

from apps.users.models.preference import UserPreference
from apps.users.models.profile import Profile, avatar_upload_to
from apps.users.models.user import User

__all__ = ["User", "Profile", "UserPreference", "avatar_upload_to"]
