"""Enumerations and magic values for the assistant app."""

from __future__ import annotations

from django.db import models


class AssistantLanguage(models.TextChoices):
    """Conversation language. Thai is first-class, not a translation."""

    TH = "th", "Thai"
    EN = "en", "English"


class ContextType(models.TextChoices):
    """What kind of content a conversation is anchored to."""

    RECIPE = "recipe", "Recipe"
    LESSON = "lesson", "Lesson"
    COURSE = "course", "Course"
    GENERAL = "general", "General"


class MessageRole(models.TextChoices):
    """Who authored a message.

    ``SYSTEM`` exists in the enum for completeness but is never stored:
    system prompts are rebuilt from the versioned template on every send,
    so user content can never overwrite or masquerade as the system role.
    """

    SYSTEM = "system", "System"
    USER = "user", "User"
    ASSISTANT = "assistant", "Assistant"


# The user-message cap. Assistant replies are uncapped — the provider decides.
MESSAGE_MAX_LENGTH = 4000

TITLE_MAX_LENGTH = 200
# Auto-titles are cut shorter so list rows stay scannable.
AUTO_TITLE_LENGTH = 80

# How many prior turns are replayed to the provider per send.
HISTORY_WINDOW = 20

# Rate-limit counter key prefix (infrastructure.cache).
RATE_LIMIT_ASSISTANT_MESSAGE = "assistant-message"
