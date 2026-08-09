"""Tags that make the bank searchable."""

from __future__ import annotations

from django.db import models
from django.db.models.functions import Lower

from apps.core.models.base import TimeStampedModel
from apps.questions.constants import TAG_NAME_MAX_LENGTH, TAG_SLUG_MAX_LENGTH


class QuestionTag(TimeStampedModel):
    """A shared label on questions.

    Tags are created implicitly when an author first uses a name — a bank one
    cannot filter is just a list. Matching is case-insensitive so "Bread" and
    "bread" are one tag. Tag assignments stay editable on frozen questions:
    organising the bank is not rewriting history.
    """

    name = models.CharField(max_length=TAG_NAME_MAX_LENGTH)
    slug = models.SlugField(
        max_length=TAG_SLUG_MAX_LENGTH,
        unique=True,
        allow_unicode=True,
    )

    class Meta:
        verbose_name = "question tag"
        verbose_name_plural = "question tags"
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                Lower("name"), name="questions_tag_name_ci_unique"
            ),
        ]

    def __str__(self) -> str:
        """Return the tag name."""
        return self.name
