"""Serializers for the compact identity payload."""

from __future__ import annotations

from typing import Any

from rest_framework import serializers


class AvatarUrlMixin(serializers.Serializer):
    """Adds an absolute ``avatar_url`` field.

    The URL must be absolute: the Next.js frontend runs on a different origin
    and cannot resolve a relative media path.
    """

    avatar_url = serializers.SerializerMethodField()

    def get_avatar_url(self, obj: Any) -> str | None:
        """Return the absolute URL of the avatar, or ``None`` when unset."""
        avatar = getattr(obj, "avatar", None)
        if not avatar:
            return None
        request = self.context.get("request")
        url = avatar.url
        return request.build_absolute_uri(url) if request is not None else url


class MeSerializer(AvatarUrlMixin):
    """The authentication-state payload returned by ``/auth/me/``.

    Deliberately small and distinct from the full profile: it is fetched on
    every frontend page load.
    """

    id = serializers.IntegerField(read_only=True)
    username = serializers.CharField(read_only=True)
    email = serializers.EmailField(read_only=True)
    is_email_verified = serializers.BooleanField(read_only=True)
    # The caller's *own* staff flag, so a client can decide whether to
    # render an admin surface at all (ADR 0022). It grants nothing: every
    # staff-widened read and every moderation write is still authorised
    # server-side, and this field never describes anyone but the caller.
    is_staff = serializers.BooleanField(read_only=True)
    experience_level = serializers.CharField(read_only=True)
