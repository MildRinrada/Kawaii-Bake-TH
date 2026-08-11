"""Django-admin registration for legal documents."""

from __future__ import annotations

from django.contrib import admin

from apps.legal.models import LegalDocument


@admin.register(LegalDocument)
class LegalDocumentAdmin(admin.ModelAdmin):
    """Read-mostly registration; the real editor is the API + back office."""

    list_display = ("kind", "title", "version", "updated_at")
    readonly_fields = ("version", "created_at", "updated_at")
