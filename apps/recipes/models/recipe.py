"""The recipe aggregate root."""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.db.models.functions import Lower

from apps.core.models.base import TimeStampedModel
from apps.recipes.constants import (
    MAX_TOTAL_MINUTES,
    RECIPE_COVER_UPLOAD_DIR,
    SLUG_MAX_LENGTH,
    SUMMARY_MAX_LENGTH,
    TITLE_MAX_LENGTH,
    Difficulty,
    RecipeStatus,
    RecipeVisibility,
)
from apps.recipes.utils import build_upload_path
from infrastructure.storage import get_media_storage


def cover_image_upload_to(instance: Recipe, filename: str) -> str:
    """Build the storage path for a recipe cover image."""
    return build_upload_path(directory=RECIPE_COVER_UPLOAD_DIR, filename=filename)


class Recipe(TimeStampedModel):
    """A bakery recipe.

    ``status`` and ``visibility`` are **orthogonal**: status is the editorial
    state (is it finished?), visibility is the audience (who may see it?). A
    single combined field cannot express "published but private", and merging
    them repeats the ``is_active``/``is_email_verified`` mistake avoided in the
    users app.

    ``published_at`` is deliberately separate from ``status``:

    * it is the correct sort key for "newest"  a recipe drafted in January and
      published in June must sort as June;
    * it is the gate that freezes the slug, so unpublish then republish does not
      unfreeze it;
    * it makes republishing idempotent.

    The many-to-many to categories is declared **here**, on the dependent side,
    so ``recipe_categories`` never references this app and stays shippable on
    its own. The lazy string reference creates no Python import edge  the same
    mechanism as ``settings.AUTH_USER_MODEL``. See
    ``docs/adr/0008-cross-app-model-references.md``.

    Reverse accessors reserved for future apps (do not reuse these names):
    ``reviews``, ``favorites``, ``gallery_posts``, ``recommendation_logs``,
    ``embedding``.
    """

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="recipes",
    )
    categories = models.ManyToManyField(
        "recipe_categories.RecipeCategory",
        related_name="recipes",
        blank=True,
    )

    title = models.CharField(max_length=TITLE_MAX_LENGTH)
    slug = models.SlugField(
        max_length=SLUG_MAX_LENGTH,
        unique=True,
        allow_unicode=True,
        help_text="Frozen once the recipe is first published.",
    )
    summary = models.CharField(
        max_length=SUMMARY_MAX_LENGTH,
        blank=True,
        help_text="One-line description shown on cards and in search results.",
    )
    description = models.TextField(blank=True)

    difficulty = models.CharField(
        max_length=20, choices=Difficulty.choices, default=Difficulty.EASY
    )
    prep_minutes = models.PositiveIntegerField(default=0)
    cook_minutes = models.PositiveIntegerField(default=0)
    total_minutes = models.PositiveIntegerField(
        default=0,
        db_index=True,
        help_text=(
            "Derived from prep + cook by the service. Stored so that sorting "
            "and filtering by total time use an index instead of an expression."
        ),
    )
    servings = models.PositiveSmallIntegerField(default=1)

    status = models.CharField(
        max_length=20,
        choices=RecipeStatus.choices,
        default=RecipeStatus.DRAFT,
        db_index=True,
    )
    visibility = models.CharField(
        max_length=20,
        choices=RecipeVisibility.choices,
        default=RecipeVisibility.PUBLIC,
        db_index=True,
    )
    published_at = models.DateTimeField(null=True, blank=True, db_index=True)

    cover_image = models.ImageField(
        upload_to=cover_image_upload_to,
        # Callable, not an instance: the migration records the reference, so
        # switching to object storage later needs no schema migration.
        storage=get_media_storage,
        blank=True,
    )

    class Meta:
        verbose_name = "recipe"
        verbose_name_plural = "recipes"
        ordering = ("-published_at", "-created_at", "-id")
        constraints = [
            models.UniqueConstraint(Lower("slug"), name="recipes_recipe_slug_ci_unique"),
            models.CheckConstraint(
                condition=models.Q(total_minutes__lte=MAX_TOTAL_MINUTES),
                name="recipes_recipe_total_minutes_max",
            ),
        ]
        indexes = [
            # The list endpoint always filters on this pair before anything else.
            models.Index(
                fields=["status", "visibility", "-published_at"],
                name="recipes_listing_idx",
            ),
            models.Index(fields=["author", "status"], name="recipes_author_status_idx"),
        ]

    def __str__(self) -> str:
        """Return the recipe title."""
        return self.title

    @property
    def is_published(self) -> bool:
        """Whether the recipe is currently published."""
        return self.status == RecipeStatus.PUBLISHED

    @property
    def slug_is_frozen(self) -> bool:
        """Whether the slug may no longer change.

        Gated on ``published_at`` rather than ``status`` so that unpublishing
        does not silently re-open a URL that has already been shared.
        """
        return self.published_at is not None
