"""App configuration for the reviews app."""

from __future__ import annotations

from django.apps import AppConfig


class ReviewsConfig(AppConfig):
    """Ratings and comments on recipes and courses.

    The dependent side toward both content apps: a review holds explicit
    nullable FKs (`recipe` / `course`  exactly one set), never a
    GenericForeignKey, so the database keeps referential integrity and the
    content apps' visibility Q builders compose across the join. Statistics
    are computed by selectors  no denormalized rating columns exist anywhere.
    See ``docs/adr/0011-review-target-architecture.md``.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.reviews"
    label = "reviews"
    verbose_name = "Reviews"
