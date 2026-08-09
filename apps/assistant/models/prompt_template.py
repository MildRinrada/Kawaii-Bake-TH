"""The versioned system-prompt template."""

from __future__ import annotations

from django.db import models
from django.db.models import Q

from apps.assistant.constants import AssistantLanguage


class PromptTemplate(models.Model):
    """One version of one system prompt, per language.

    Prompt text is data, not code: changing how the assistant behaves must
    not require a deploy, and must not silently change how **old**
    conversations behave. A new behaviour is a new row with a new
    ``version``; flipping ``is_active`` routes new conversations to it while
    existing ones keep resolving their stamped ``prompt_version``. Rows are
    never edited in place once referenced — the partial unique guarantees at
    most one active version per ``(name, language)``.
    """

    name = models.CharField(max_length=50)
    language = models.CharField(max_length=5, choices=AssistantLanguage.choices)
    version = models.CharField(max_length=20)
    template = models.TextField()
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "prompt template"
        verbose_name_plural = "prompt templates"
        ordering = ("name", "language", "-created_at")
        constraints = [
            models.UniqueConstraint(
                fields=("name", "language", "version"),
                name="assistant_prompt_version_unique",
            ),
            models.UniqueConstraint(
                fields=("name", "language"),
                condition=Q(is_active=True),
                name="assistant_prompt_one_active",
            ),
        ]

    def __str__(self) -> str:
        """Return the template description."""
        flag = " (active)" if self.is_active else ""
        return f"{self.name}/{self.language} v{self.version}{flag}"
