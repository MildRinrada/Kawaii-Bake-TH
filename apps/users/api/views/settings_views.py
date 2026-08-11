"""The read-only settings composition endpoint."""

from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.common.api.views import ServiceAPIView
from apps.notifications.selectors import notification_selector
from apps.users.api.serializers.settings_serializers import MySettingsSerializer
from apps.users.selectors import profile_selector
from apps.users.services import profile_service


class MySettingsView(ServiceAPIView):
    """GET /me/settings/  one read across the caller's settings.

    An API-edge composition in the favorites-stitching mould: the view
    reads each domain through its own public boundary and stitches the
    blocks. Notification preferences stay owned by ``notifications`` 
    this endpoint cannot write anything, so ownership cannot drift
    (ADR 0020 §7).
    """

    permission_classes = (IsAuthenticated,)

    @extend_schema(responses={200: MySettingsSerializer}, tags=["users"])
    def get(self, request: Request) -> Response:
        """Return profile, preferences, notification settings and completion."""
        profile = profile_service.get_own_profile(user_id=request.user.id)
        payload = {
            "profile": profile,
            "preferences": profile_service.get_own_preference(
                user_id=request.user.id
            ),
            "notifications": notification_selector.effective_preferences(
                user_id=request.user.id
            ),
            "profile_completion": profile_selector.profile_completion(profile),
        }
        return Response(
            MySettingsSerializer(payload, context=self.get_serializer_context()).data
        )
