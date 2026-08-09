"""Django admin registration for users, profiles and preferences."""

from __future__ import annotations

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.http import HttpRequest

from apps.users.forms.admin_forms import UserAdminChangeForm, UserAdminCreationForm
from apps.users.models import Profile, User, UserPreference
from apps.users.repositories.user_repository import ensure_related_records


class ProfileInline(admin.StackedInline):
    """Edit a user's profile alongside the account."""

    model = Profile
    can_delete = False
    extra = 0


class UserPreferenceInline(admin.StackedInline):
    """Edit a user's preferences alongside the account."""

    model = UserPreference
    can_delete = False
    extra = 0


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Admin for the custom user model."""

    form = UserAdminChangeForm
    add_form = UserAdminCreationForm
    inlines = (ProfileInline, UserPreferenceInline)

    list_display = ("username", "email", "is_active", "is_email_verified", "is_staff")
    list_filter = ("is_active", "is_email_verified", "is_staff", "is_superuser")
    search_fields = ("email", "username")
    ordering = ("-created_at",)
    readonly_fields = ("last_login", "created_at", "updated_at", "email_verified_at")

    fieldsets = (
        (None, {"fields": ("email", "username", "password")}),
        (
            "Status",
            {
                "fields": (
                    "is_active",
                    "is_email_verified",
                    "email_verified_at",
                    "deactivated_at",
                )
            },
        ),
        (
            "Permissions",
            {"fields": ("is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        ("Timestamps", {"fields": ("last_login", "created_at", "updated_at")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "username", "password1", "password2"),
            },
        ),
    )

    def save_model(
        self, request: HttpRequest, obj: User, form: object, change: bool
    ) -> None:
        """Persist the user and guarantee its profile and preference rows exist.

        The admin bypasses ``UserManager.create_user``, so the related rows are
        reconciled here. ``ensure_related_records`` is idempotent.
        """
        super().save_model(request, obj, form, change)
        if not change:
            ensure_related_records(user=obj)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    """Read-mostly admin for profiles."""

    list_display = ("user", "display_name", "experience_level")
    list_filter = ("experience_level",)
    search_fields = ("user__email", "user__username", "display_name")
    raw_id_fields = ("user",)


@admin.register(UserPreference)
class UserPreferenceAdmin(admin.ModelAdmin):
    """Read-mostly admin for user preferences."""

    list_display = ("user", "profile_visibility", "theme", "preferred_difficulty")
    list_filter = ("profile_visibility", "theme", "preferred_difficulty")
    search_fields = ("user__email", "user__username")
    raw_id_fields = ("user",)
