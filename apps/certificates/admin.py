"""Django admin for the certificates app.

Certificates are immutable records and achievements are append-only facts —
both are read-only here (revocation is a service concern, exposed as an
admin action rather than field editing). Badge definitions are the one
curated surface: system-owned rows with no public CRUD API.
"""

from __future__ import annotations

from django.contrib import admin

from apps.certificates.models import Achievement, BadgeDefinition, Certificate
from apps.certificates.repositories import certificate_repository


@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    """Inspect certificates; the only action is revocation."""

    list_display = (
        "certificate_number",
        "user",
        "course_title",
        "issued_at",
        "revoked_at",
    )
    list_filter = ("revoked_at",)
    search_fields = ("certificate_number", "student_name", "course_title")
    raw_id_fields = ("user", "course")
    actions = ("revoke_certificates",)

    def has_add_permission(self, request) -> bool:  # noqa: D102
        return False

    def has_change_permission(self, request, obj=None) -> bool:  # noqa: D102
        return False

    def has_delete_permission(self, request, obj=None) -> bool:  # noqa: D102
        return False

    @admin.action(description="Revoke selected certificates")
    def revoke_certificates(self, request, queryset) -> None:
        """Stamp ``revoked_at`` on the selection, idempotently."""
        for certificate in queryset:
            certificate_repository.revoke(certificate=certificate)


@admin.register(Achievement)
class AchievementAdmin(admin.ModelAdmin):
    """Inspect earned achievements — strictly read-only."""

    list_display = ("id", "user", "achievement_type", "awarded_at")
    list_filter = ("achievement_type",)
    raw_id_fields = ("user", "badge")

    def has_add_permission(self, request) -> bool:  # noqa: D102
        return False

    def has_change_permission(self, request, obj=None) -> bool:  # noqa: D102
        return False

    def has_delete_permission(self, request, obj=None) -> bool:  # noqa: D102
        return False


@admin.register(BadgeDefinition)
class BadgeDefinitionAdmin(admin.ModelAdmin):
    """Curate badge presentation; the slug is the identity and stays fixed."""

    list_display = ("slug", "title_th", "title_en", "icon", "is_active")
    list_filter = ("is_active",)
    readonly_fields = ("slug",)
