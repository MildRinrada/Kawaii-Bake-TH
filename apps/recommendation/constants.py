"""Constants for recommendation scoring and substitution.

Every scoring weight lives here, named  no magic numbers inside the
pipeline. Changing how recommendations rank is an edit to this file plus its
tests, reviewable as a diff of declared policy (the ``XP_RULES`` precedent
from gamification, ADR 0015).
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Candidate generation
# ---------------------------------------------------------------------------

# How many of the newest publicly visible items enter the scoring pool.
# Bounded on purpose: ranking is done in application code, so the pool must
# be a LIMIT-ed query, never the whole table. Raising this is a policy
# change; replacing it with a search-engine-backed pool is the declared
# future seam (ADR 0018 §16).
CANDIDATE_POOL_SIZE = 200

# A review at or above this rating counts as a positive signal.
POSITIVE_REVIEW_MIN_RATING = 4

# ---------------------------------------------------------------------------
# Interest weights  how strongly each kind of evidence marks a category
# ---------------------------------------------------------------------------

# The user explicitly picked the category on their profile.
INTEREST_PROFILE_CATEGORY = 2.0
# The category appears on something the user favorited.
INTEREST_FAVORITE = 1.0
# The category appears on something the user reviewed positively.
INTEREST_POSITIVE_REVIEW = 1.0
# The category appears on a course the user enrolled in.
INTEREST_ENROLLMENT = 1.0

# ---------------------------------------------------------------------------
# Scoring weights
# ---------------------------------------------------------------------------

# Multiplier applied to the (capped) sum of interest weights a candidate's
# categories collect.
W_CATEGORY_MATCH = 2.0
# Cap on the raw interest sum, so one obsessively favorited category cannot
# drown every other feature.
CATEGORY_SCORE_CAP = 8.0

# The candidate's author/instructor also made something the user favorited
# or reviewed positively.
W_AUTHOR_AFFINITY = 3.0

# Popularity: average rating (0–5) and capped counts. Caps keep old viral
# content from permanently outscoring everything newer.
W_RATING_AVERAGE = 1.0
W_RATING_COUNT = 0.1
RATING_COUNT_CAP = 20
W_FAVORITE_COUNT = 0.1
FAVORITE_COUNT_CAP = 20

# Freshness: a linear bonus that decays to zero over the window.
W_RECENCY = 2.0
RECENCY_WINDOW_DAYS = 90

# The candidate's difficulty fits the user's declared experience level.
W_DIFFICULTY_FIT = 1.0

# Difficulty values each experience level is assumed comfortable with.
# Keys are ``users.BakingExperienceLevel`` values; values are
# ``recipes.Difficulty`` / ``courses.Difficulty`` values. Kept as plain
# strings so this app imports no other app's constants module.
EXPERIENCE_DIFFICULTY_FIT: dict[str, tuple[str, ...]] = {
    "beginner": ("easy",),
    "intermediate": ("easy", "medium"),
    "advanced": ("medium", "hard"),
    "professional": ("hard", "expert"),
}

# ---------------------------------------------------------------------------
# Diversification
# ---------------------------------------------------------------------------

# Score penalty per already-selected result sharing the candidate's primary
# category. Deliberately smaller than W_AUTHOR_AFFINITY: variety may break
# ties and near-ties, but must never promote a clearly weaker candidate
# over a clearly stronger one.
DIVERSITY_PENALTY = 1.5

# ---------------------------------------------------------------------------
# Explanation reason codes  machine-readable, rendered by the frontend
# ---------------------------------------------------------------------------

REASON_PROFILE_CATEGORY = "matches_your_favorite_categories"
REASON_SIMILAR_TO_FAVORITES = "similar_to_your_favorites"
REASON_SIMILAR_TO_REVIEWS = "similar_to_content_you_reviewed"
REASON_BASED_ON_COURSES = "based_on_your_courses"
REASON_AUTHOR_AFFINITY = "from_a_creator_you_like"
REASON_HIGHLY_RATED = "highly_rated"
REASON_POPULAR = "popular"
REASON_NEW = "recently_published"

# Fixed presentation order: evidence-backed personal reasons first, global
# ones last. Determinism of the reason list is part of the API contract.
REASON_ORDER: tuple[str, ...] = (
    REASON_PROFILE_CATEGORY,
    REASON_SIMILAR_TO_FAVORITES,
    REASON_SIMILAR_TO_REVIEWS,
    REASON_BASED_ON_COURSES,
    REASON_AUTHOR_AFFINITY,
    REASON_HIGHLY_RATED,
    REASON_POPULAR,
    REASON_NEW,
)

# Thresholds behind the global reasons.
HIGHLY_RATED_MIN_AVERAGE = 4.0
HIGHLY_RATED_MIN_COUNT = 3
POPULAR_MIN_FAVORITES = 3

# ---------------------------------------------------------------------------
# Substitution
# ---------------------------------------------------------------------------

# Confidence labels  deliberately coarse. The registry stores curated
# kitchen wisdom, not measured equivalence; three buckets are all the
# precision that honestly exists (ADR 0018 §12).
CONFIDENCE_HIGH = "high"
CONFIDENCE_MEDIUM = "medium"
CONFIDENCE_LOW = "low"

INGREDIENT_QUERY_MAX_LENGTH = 120
