"""The recipe category taxonomy."""

from __future__ import annotations

from django.db import models
from django.db.models.functions import Lower

from apps.common.utils.files import build_upload_path
from apps.core.models.base import TimeStampedModel
from apps.recipe_categories.constants import (
    CATEGORY_DEFAULT_ORDERING,
    CATEGORY_DESCRIPTION_MAX_LENGTH,
    CATEGORY_ICON_MAX_LENGTH,
    CATEGORY_IMAGE_UPLOAD_DIR,
    CATEGORY_NAME_MAX_LENGTH,
    CATEGORY_SLUG_MAX_LENGTH,
)
from infrastructure.storage import get_media_storage


def category_image_upload_to(instance: RecipeCategory, filename: str) -> str:
    """Build the storage path for a category tile photo."""
    return build_upload_path(
        directory=CATEGORY_IMAGE_UPLOAD_DIR, filename=filename
    )


class RecipeCategory(TimeStampedModel):
    """A category a recipe can belong to, such as bread or macaron.

    This app is deliberately a leaf: it never references ``recipes``. The
    many-to-many is declared on ``Recipe``, which is the dependent side, so
    ``recipe_categories`` remains shippable on its own.

    There is no ``parent`` field and no ``recipe_count`` column. A self-relation
    on a table of roughly twenty rows is trivial to add when hierarchy is
    actually needed, and the count is one ``annotate(Count(...))`` in the
    selector  a stored counter would be a second source of truth able to drift.

    Reverse accessors reserved for future apps: ``recipes`` (taken by the
    many-to-many on ``Recipe``), ``courses``, ``favorites``.
    """

    name = models.CharField(max_length=CATEGORY_NAME_MAX_LENGTH)
    slug = models.SlugField(
        max_length=CATEGORY_SLUG_MAX_LENGTH,
        unique=True,
        allow_unicode=True,
        help_text="Stable identifier used in URLs and filter parameters.",
    )
    description = models.CharField(
        max_length=CATEGORY_DESCRIPTION_MAX_LENGTH, blank=True
    )
    icon = models.CharField(
        max_length=CATEGORY_ICON_MAX_LENGTH,
        blank=True,
        help_text="Frontend icon key or emoji.",
    )
    # The tile photo the home page and filter boxes show. Optional: when
    # unset the frontend falls back to its built-in artwork for known
    # slugs, so seeding a fresh database still looks finished.
    image = models.ImageField(
        upload_to=category_image_upload_to,
        storage=get_media_storage,
        blank=True,
        help_text="Tile photo shown on the home page and category boxes.",
    )
    display_order = models.PositiveSmallIntegerField(
        default=0, help_text="Lower values sort first."
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Inactive categories stay assigned but are hidden from listings.",
    )

    class Meta:
        verbose_name = "recipe category"
        verbose_name_plural = "recipe categories"
        ordering = CATEGORY_DEFAULT_ORDERING
        constraints = [
            models.UniqueConstraint(
                Lower("slug"), name="recipe_categories_slug_ci_unique"
            ),
        ]

    def __str__(self) -> str:
        """Return the category name."""
        return self.name
