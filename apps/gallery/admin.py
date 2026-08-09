"""Django admin for the gallery app."""

from __future__ import annotations

from django.contrib import admin

from apps.gallery.models import GalleryImage, GalleryPost


class GalleryImageInline(admin.TabularInline):
    """Images inline on their post."""

    model = GalleryImage
    extra = 0
    readonly_fields = ("image", "position")

    def has_add_permission(self, request, obj=None) -> bool:  # noqa: D102
        return False


@admin.register(GalleryPost)
class GalleryPostAdmin(admin.ModelAdmin):
    """Browse and, if needed, unpublish posts."""

    list_display = ("id", "author", "status", "recipe", "course", "created_at")
    list_filter = ("status",)
    search_fields = ("caption", "author__username")
    raw_id_fields = ("author", "recipe", "course")
    inlines = (GalleryImageInline,)
