"""Serializers for the authentication endpoints.

These validate the *message*: presence, type, length, shape. Domain rules
(uniqueness, reserved handles, password strength) belong to ``validators/`` and
run inside the services, so they hold for every caller  not just HTTP.
"""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.common.api.serializers import StrictSerializer
from apps.users.constants import (
    NAME_PART_MAX_LENGTH,
    USERNAME_MAX_LENGTH,
    USERNAME_MIN_LENGTH,
)
from apps.users.validators.user_validator import validate_username


class RegistrationSerializer(StrictSerializer):
    """Validates a sign-up payload.

    The legal name is mandatory: certificates print it, and a certificate
    naming a handle is not a credential. ``accept_terms`` must be an
    explicit ``true``  PDPA consent is an action the user takes, never a
    default the form ships with.
    """

    email = serializers.EmailField(max_length=254)
    username = serializers.CharField(
        min_length=USERNAME_MIN_LENGTH,
        max_length=USERNAME_MAX_LENGTH,
        # Passing the domain rule as a field validator is what makes DRF
        # translate its Django ValidationError into a clean 400.
        validators=[validate_username],
    )
    first_name = serializers.CharField(max_length=NAME_PART_MAX_LENGTH)
    last_name = serializers.CharField(max_length=NAME_PART_MAX_LENGTH)
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    password_confirm = serializers.CharField(write_only=True, trim_whitespace=False)
    accept_terms = serializers.BooleanField()

    def validate_accept_terms(self, value: bool) -> bool:
        """Reject a registration that does not carry explicit consent."""
        if not value:
            raise serializers.ValidationError(
                "You must accept the terms of service and privacy policy."
            )
        return value

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """Confirm the two password entries match.

        Strength is validated in the service, where Django's configured
        validators can also see the user's own attributes.
        """
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError(
                {"password_confirm": ["The two password entries do not match."]}
            )
        return attrs


class UsernameAvailabilityQuerySerializer(StrictSerializer):
    """Validates the ``?username=`` query of the availability check.

    Only presence and a length guard: a *malformed* handle is answered with
    ``available: false`` rather than a 400, because the caller is a live
    keystroke check and every answer shape must be renderable inline.
    """

    username = serializers.CharField(max_length=254)


class UsernameAvailabilityResponseSerializer(serializers.Serializer):
    """Documents the availability-check response."""

    username = serializers.CharField(read_only=True)
    available = serializers.BooleanField(read_only=True)


class LoginSerializer(StrictSerializer):
    """Validates a sign-in payload."""

    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    remember_me = serializers.BooleanField(required=False, default=False)


class PasswordResetRequestSerializer(StrictSerializer):
    """Validates a "send me a reset link" payload."""

    email = serializers.EmailField(max_length=254)


class PasswordResetConfirmSerializer(StrictSerializer):
    """Validates a reset-link submission."""

    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, trim_whitespace=False)


class PasswordChangeSerializer(StrictSerializer):
    """Validates a self-service password change."""

    current_password = serializers.CharField(write_only=True, trim_whitespace=False)
    new_password = serializers.CharField(write_only=True, trim_whitespace=False)


class EmailVerificationConfirmSerializer(StrictSerializer):
    """Validates a verification-link submission."""

    uid = serializers.CharField()
    token = serializers.CharField()


class AuthenticatedResponseSerializer(serializers.Serializer):
    """Documents the shape returned by a successful sign-in."""

    status = serializers.CharField(read_only=True)
    user = serializers.DictField(read_only=True)
