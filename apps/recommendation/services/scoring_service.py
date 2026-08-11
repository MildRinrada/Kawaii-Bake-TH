"""The pure heart of recommendation: features, scoring, ranking, diversity.

Everything in this module is a deterministic function of its arguments  no
database, no clock, no randomness. ``now`` is a parameter precisely so the
same facts always produce the same ranking, in production and in tests
(ADR 0018 §8). Candidate generation and fact fetching live in
``recommendation_service``; this module never knows where facts came from.

Kept as one module on purpose: splitting feature extraction, scoring and
ranking into three files would triple the surface of what is a page of pure
functions (the "no abstraction for symmetry" rule).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from apps.recommendation.constants import (
    CATEGORY_SCORE_CAP,
    DIVERSITY_PENALTY,
    EXPERIENCE_DIFFICULTY_FIT,
    FAVORITE_COUNT_CAP,
    HIGHLY_RATED_MIN_AVERAGE,
    HIGHLY_RATED_MIN_COUNT,
    POPULAR_MIN_FAVORITES,
    RATING_COUNT_CAP,
    REASON_AUTHOR_AFFINITY,
    REASON_BASED_ON_COURSES,
    REASON_HIGHLY_RATED,
    REASON_NEW,
    REASON_ORDER,
    REASON_POPULAR,
    REASON_PROFILE_CATEGORY,
    REASON_SIMILAR_TO_FAVORITES,
    REASON_SIMILAR_TO_REVIEWS,
    RECENCY_WINDOW_DAYS,
    W_AUTHOR_AFFINITY,
    W_CATEGORY_MATCH,
    W_DIFFICULTY_FIT,
    W_FAVORITE_COUNT,
    W_RATING_AVERAGE,
    W_RATING_COUNT,
    W_RECENCY,
)


@dataclass(frozen=True)
class TasteContext:
    """Everything scoring may know about the viewer's taste.

    Built once per request from behavioral facts; empty for anonymous or
    brand-new users, in which case scoring degrades to the global features
    only  that *is* the cold-start strategy, not a separate code path.
    """

    interest_weights: dict[str, float] = field(default_factory=dict)
    profile_category_slugs: frozenset[str] = frozenset()
    favorite_category_slugs: frozenset[str] = frozenset()
    review_category_slugs: frozenset[str] = frozenset()
    course_category_slugs: frozenset[str] = frozenset()
    liked_creator_ids: frozenset[int] = frozenset()
    fit_difficulties: frozenset[str] = frozenset()


EMPTY_CONTEXT = TasteContext()


def context_fit_difficulties(experience_level: str) -> frozenset[str]:
    """Difficulties assumed comfortable for an experience level."""
    return frozenset(EXPERIENCE_DIFFICULTY_FIT.get(experience_level, ()))


@dataclass(frozen=True)
class Candidate:
    """One scoring input, already shaped identically for recipes and courses."""

    id: int
    creator_id: int
    difficulty: str
    published_at: datetime | None
    category_slugs: tuple[str, ...]


@dataclass(frozen=True)
class ScoredCandidate:
    """A candidate with its score and the evidence behind it."""

    id: int
    score: float
    reasons: tuple[str, ...]
    primary_category: str


def score_candidate(
    *,
    candidate: Candidate,
    context: TasteContext,
    rating_average: float,
    rating_count: int,
    favorite_count: int,
    now: datetime,
) -> ScoredCandidate:
    """Score one candidate against the viewer's taste context.

    Every term is additive and individually explainable; the reasons list is
    derived from the same evidence the score is, so an explanation can never
    claim something the score did not use.

    Args:
        candidate: The candidate's facts.
        context: The viewer's taste context (``EMPTY_CONTEXT`` = cold start).
        rating_average: Average active-review rating, 0 when unreviewed.
        rating_count: Number of active reviews.
        favorite_count: Number of users who favorited the candidate.
        now: The reference time for the recency feature.

    Returns:
        The scored candidate with its reason codes.
    """
    reasons: set[str] = set()
    score = 0.0
    categories = set(candidate.category_slugs)

    interest = sum(
        context.interest_weights.get(slug, 0.0) for slug in candidate.category_slugs
    )
    score += W_CATEGORY_MATCH * min(interest, CATEGORY_SCORE_CAP)
    if categories & context.profile_category_slugs:
        reasons.add(REASON_PROFILE_CATEGORY)
    if categories & context.favorite_category_slugs:
        reasons.add(REASON_SIMILAR_TO_FAVORITES)
    if categories & context.review_category_slugs:
        reasons.add(REASON_SIMILAR_TO_REVIEWS)
    if categories & context.course_category_slugs:
        reasons.add(REASON_BASED_ON_COURSES)

    if candidate.creator_id in context.liked_creator_ids:
        score += W_AUTHOR_AFFINITY
        reasons.add(REASON_AUTHOR_AFFINITY)

    score += W_RATING_AVERAGE * rating_average
    score += W_RATING_COUNT * min(rating_count, RATING_COUNT_CAP)
    score += W_FAVORITE_COUNT * min(favorite_count, FAVORITE_COUNT_CAP)
    if rating_average >= HIGHLY_RATED_MIN_AVERAGE and rating_count >= HIGHLY_RATED_MIN_COUNT:
        reasons.add(REASON_HIGHLY_RATED)
    if favorite_count >= POPULAR_MIN_FAVORITES:
        reasons.add(REASON_POPULAR)

    if candidate.published_at is not None:
        age_days = (now - candidate.published_at).total_seconds() / 86_400
        if 0 <= age_days < RECENCY_WINDOW_DAYS:
            score += W_RECENCY * (1 - age_days / RECENCY_WINDOW_DAYS)
            reasons.add(REASON_NEW)

    if candidate.difficulty in context.fit_difficulties:
        score += W_DIFFICULTY_FIT

    return ScoredCandidate(
        id=candidate.id,
        score=score,
        reasons=tuple(code for code in REASON_ORDER if code in reasons),
        primary_category=candidate.category_slugs[0] if candidate.category_slugs else "",
    )


def rank(scored: list[ScoredCandidate]) -> list[ScoredCandidate]:
    """Order by score, ties broken by ascending id  fully deterministic."""
    return sorted(scored, key=lambda item: (-item.score, item.id))


def diversify(ranked: list[ScoredCandidate]) -> list[ScoredCandidate]:
    """Reorder a ranked list so one category does not monopolise the top.

    Deterministic greedy selection: at each step take the candidate whose
    score, minus ``DIVERSITY_PENALTY`` per already-selected result sharing
    its primary category, is highest  ties broken by original rank. The
    penalty is bounded, so a clearly stronger candidate still wins; only
    near-ties get spread across categories.

    Args:
        ranked: The output of :func:`rank`.

    Returns:
        The same candidates, reordered.
    """
    remaining = list(ranked)
    selected: list[ScoredCandidate] = []
    category_counts: dict[str, int] = {}

    while remaining:
        best_index = 0
        best_key: tuple[float, int] | None = None
        for index, item in enumerate(remaining):
            penalty = DIVERSITY_PENALTY * category_counts.get(item.primary_category, 0)
            key = (-(item.score - penalty), index)
            if best_key is None or key < best_key:
                best_key = key
                best_index = index
        chosen = remaining.pop(best_index)
        selected.append(chosen)
        if chosen.primary_category:
            category_counts[chosen.primary_category] = (
                category_counts.get(chosen.primary_category, 0) + 1
            )
    return selected
