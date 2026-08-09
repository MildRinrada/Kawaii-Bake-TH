"""Enumerations for the favorites app."""

from __future__ import annotations

from django.db import models


class FavoriteTargetKind(models.TextChoices):
    """What a favorite points at."""

    RECIPE = "recipe", "Recipe"
    COURSE = "course", "Course"
