"""Enumerations and magic values for the recipes app."""

from __future__ import annotations

from django.db import models


class RecipeStatus(models.TextChoices):
    """Editorial state of a recipe.

    Orthogonal to :class:`RecipeVisibility`  status answers "is it finished?",
    visibility answers "who may see it?". Conflating them is the same mistake as
    conflating ``is_active`` with ``is_email_verified`` on ``User``.
    """

    DRAFT = "draft", "Draft"
    PUBLISHED = "published", "Published"
    ARCHIVED = "archived", "Archived"


class RecipeVisibility(models.TextChoices):
    """Audience for a published recipe.

    ``UNLISTED`` is the asymmetric one: reachable by direct link, absent from
    every listing and from search.
    """

    PUBLIC = "public", "Anyone"
    UNLISTED = "unlisted", "Anyone with the link"
    PRIVATE = "private", "Only me"


class RecipeScope(models.TextChoices):
    """Which slice of recipes a list request is asking for."""

    PUBLIC = "public", "Publicly visible recipes"
    MINE = "mine", "My own recipes, any status"
    ALL = "all", "Everything (staff only)"


class Difficulty(models.TextChoices):
    """How demanding a recipe is."""

    EASY = "easy", "Easy"
    MEDIUM = "medium", "Medium"
    HARD = "hard", "Hard"
    EXPERT = "expert", "Expert"


class Unit(models.TextChoices):
    """Measurement units for ingredient quantities."""

    GRAM = "g", "g"
    KILOGRAM = "kg", "kg"
    MILLILITRE = "ml", "ml"
    LITRE = "l", "l"
    TEASPOON = "tsp", "tsp"
    TABLESPOON = "tbsp", "tbsp"
    CUP = "cup", "cup"
    PIECE = "piece", "piece"
    PINCH = "pinch", "pinch"
    SLICE = "slice", "slice"
    TO_TASTE = "to_taste", "to taste"


class NutritionBasis(models.TextChoices):
    """What the nutrition figures are measured against.

    Ships in Phase 2 even though nothing computes nutrition yet: without it
    every stored number is ambiguous, and no later migration could repair that.
    """

    PER_SERVING = "per_serving", "Per serving"
    PER_100G = "per_100g", "Per 100 g"


class NutritionSource(models.TextChoices):
    """Where the nutrition figures came from.

    Phase 2 only ever writes ``MANUAL``. ``ESTIMATED`` exists so the future
    estimator is an additive change, and so the frontend can render an
    "estimated, not verified" disclaimer from day one.
    """

    MANUAL = "manual", "Entered by the author"
    ESTIMATED = "estimated", "Estimated automatically"
    VERIFIED = "verified", "Verified"


class Ordering(models.TextChoices):
    """Permitted values of the ``ordering`` query parameter."""

    NEWEST = "newest", "Newest first"
    OLDEST = "oldest", "Oldest first"
    TITLE = "title", "Title A–Z"
    QUICKEST = "quickest", "Shortest total time"
    DIFFICULTY = "difficulty", "Easiest first"
    POPULAR = "popular", "Most popular"
    RELEVANCE = "relevance", "Best match"


# Maps the public ordering name to concrete ORM ordering.
#
# Every entry ends with `-id`. Without that tiebreaker, rows sharing a sort key
# reshuffle between pages and users see duplicates and gaps.
#
# `POPULAR` is a deliberate placeholder: it sorts by publication date until
# `favorites`/`reviews` exist. Because the mapping lives here, switching it to
# `-favorite_count` later is one line and changes no part of the API contract.
ORDERING_MAP: dict[str, tuple[str, ...]] = {
    Ordering.NEWEST: ("-published_at", "-created_at", "-id"),
    Ordering.OLDEST: ("published_at", "created_at", "-id"),
    Ordering.TITLE: ("title", "-id"),
    Ordering.QUICKEST: ("total_minutes", "-id"),
    Ordering.DIFFICULTY: ("difficulty_rank", "-id"),
    Ordering.POPULAR: ("-published_at", "-created_at", "-id"),
    Ordering.RELEVANCE: (),
}

# `easy/medium/hard/expert` sorts alphabetically as easy, expert, hard, medium.
# Ordering by difficulty therefore needs an explicit ordinal, not the column.
DIFFICULTY_RANK: dict[str, int] = {
    Difficulty.EASY: 1,
    Difficulty.MEDIUM: 2,
    Difficulty.HARD: 3,
    Difficulty.EXPERT: 4,
}

# --------------------------------------------------------------------------
# Field limits
# --------------------------------------------------------------------------
TITLE_MIN_LENGTH = 3
TITLE_MAX_LENGTH = 160
SLUG_MAX_LENGTH = 180
SLUG_BASE_MAX_LENGTH = 160
SUMMARY_MAX_LENGTH = 300
INGREDIENT_NAME_MAX_LENGTH = 120
INGREDIENT_NOTE_MAX_LENGTH = 120
INGREDIENT_GROUP_MAX_LENGTH = 60
STEP_BODY_MAX_LENGTH = 2000
IMAGE_CAPTION_MAX_LENGTH = 200

MIN_SERVINGS = 1
MAX_SERVINGS = 100

MIN_MINUTES = 0
# Seven days: sourdough starters and long ferments are legitimately this slow.
MAX_TOTAL_MINUTES = 60 * 24 * 7

MAX_INGREDIENTS_PER_RECIPE = 50
MAX_STEPS_PER_RECIPE = 50
MAX_IMAGES_PER_RECIPE = 10
MAX_CATEGORIES_PER_RECIPE = 5

SEARCH_TERM_MAX_LENGTH = 100

# Slug generation
SLUG_COLLISION_ATTEMPTS = 5
SLUG_SUFFIX_BYTES = 3

# --------------------------------------------------------------------------
# Media
# --------------------------------------------------------------------------
RECIPE_COVER_UPLOAD_DIR = "recipes/covers"
RECIPE_IMAGE_UPLOAD_DIR = "recipes/gallery"
RECIPE_STEP_UPLOAD_DIR = "recipes/steps"
RECIPE_IMAGE_MAX_SIZE_BYTES = 5 * 1024 * 1024
# SVG is excluded: it can carry script and would be stored XSS.
ALLOWED_RECIPE_IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".webp"})
ALLOWED_RECIPE_IMAGE_FORMATS = frozenset({"JPEG", "PNG", "WEBP"})

# --------------------------------------------------------------------------
# Slugs that would shadow a route under /api/v1/recipes/.
# Route literals are also declared before `<str:slug>`; this is the second line
# of defence.
# --------------------------------------------------------------------------
RESERVED_RECIPE_SLUGS = frozenset(
    {
        "archive",
        "archived",
        "create",
        "draft",
        "drafts",
        "me",
        "new",
        "newest",
        "popular",
        "publish",
        "search",
        "unpublish",
    }
)
