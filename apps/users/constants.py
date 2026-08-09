"""Enumerations and magic values for the users app."""

from __future__ import annotations

from django.db import models


class BakingExperienceLevel(models.TextChoices):
    """How experienced a baker considers themselves."""

    BEGINNER = "beginner", "Beginner"
    INTERMEDIATE = "intermediate", "Intermediate"
    ADVANCED = "advanced", "Advanced"
    PROFESSIONAL = "professional", "Professional"


class BakingCategory(models.TextChoices):
    """Baking category slugs — historical, kept for migrations.

    Phase 1 stored these slugs as JSON on ``Profile``; Phase 2 seeded the
    ``recipe_categories`` taxonomy from them; Phase 14 completed the
    promised backfill to a real many-to-many (ADR 0020). Live validation
    now runs against the taxonomy via ``category_selector.resolve_slugs``
    — this enum remains only because the Phase 2 seed migration imports
    it. Do not use it for new validation.
    """

    BREAD = "bread", "Bread"
    CAKE = "cake", "Cake"
    COOKIES = "cookies", "Cookies"
    PASTRY = "pastry", "Pastry"
    PIE = "pie", "Pie & Tart"
    MACARON = "macaron", "Macaron"
    CHOCOLATE = "chocolate", "Chocolate"
    DECORATING = "decorating", "Cake Decorating"
    VEGAN = "vegan", "Vegan Baking"
    GLUTEN_FREE = "gluten_free", "Gluten Free"


class ProfileVisibility(models.TextChoices):
    """Who may view a user's profile."""

    PUBLIC = "public", "Anyone"
    MEMBERS = "members", "Signed-in members"
    PRIVATE = "private", "Only me"


class DietaryRestriction(models.TextChoices):
    """Dietary constraints used to tailor learning content."""

    NONE = "none", "No restrictions"
    VEGAN = "vegan", "Vegan"
    VEGETARIAN = "vegetarian", "Vegetarian"
    GLUTEN_FREE = "gluten_free", "Gluten free"
    DAIRY_FREE = "dairy_free", "Dairy free"
    NUT_FREE = "nut_free", "Nut free"
    EGG_FREE = "egg_free", "Egg free"


class Theme(models.TextChoices):
    """Preferred interface theme."""

    SYSTEM = "system", "Match system"
    LIGHT = "light", "Light"
    DARK = "dark", "Dark"


class PreferredLanguage(models.TextChoices):
    """The user's preferred content language.

    Deliberately the same code set as ``assistant.AssistantLanguage`` —
    a compatibility test pins that, so the assistant can default a
    conversation to this preference without translation glue. Thai first:
    it is the platform default, not a fallback (ADR 0020 §8).
    """

    TH = "th", "Thai"
    EN = "en", "English"


# --------------------------------------------------------------------------
# Field limits
# --------------------------------------------------------------------------
USERNAME_MIN_LENGTH = 3
USERNAME_MAX_LENGTH = 30
DISPLAY_NAME_MAX_LENGTH = 60
BIO_MAX_LENGTH = 500
LOCATION_MAX_LENGTH = 120

MAX_FAVORITE_CATEGORIES = 10
MAX_DIETARY_RESTRICTIONS = 6

MIN_AGE_YEARS = 13
MAX_AGE_YEARS = 120

WEEKLY_GOAL_MIN_MINUTES = 0
WEEKLY_GOAL_MAX_MINUTES = 60 * 40
WEEKLY_GOAL_DEFAULT_MINUTES = 60

# --------------------------------------------------------------------------
# Avatar upload rules
# --------------------------------------------------------------------------
AVATAR_UPLOAD_DIR = "avatars"
AVATAR_MAX_SIZE_BYTES = 2 * 1024 * 1024
# SVG is deliberately excluded: it can carry script and would be stored XSS.
ALLOWED_AVATAR_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".webp"})
ALLOWED_AVATAR_FORMATS = frozenset({"JPEG", "PNG", "WEBP"})

# --------------------------------------------------------------------------
# Usernames that must never be claimed by a user, because they collide with
# routes or would let a profile impersonate the platform.
# --------------------------------------------------------------------------
RESERVED_USERNAMES = frozenset(
    {
        "admin",
        "administrator",
        "api",
        "auth",
        "kawaiibake",
        "login",
        "logout",
        "me",
        "media",
        "account",
        "moderator",
        "preferences",
        "profile",
        "register",
        "root",
        "settings",
        "signup",
        "staff",
        "static",
        "support",
        "system",
        "u",
        "user",
        "users",
    }
)
