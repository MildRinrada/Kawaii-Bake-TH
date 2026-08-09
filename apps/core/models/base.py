"""Abstract base models shared by every feature app."""

from __future__ import annotations

from django.db import models


class TimeStampedModel(models.Model):
    """Adds creation and modification timestamps to a model.

    ``created_at`` is indexed because listings across the platform order by it.
    """

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
