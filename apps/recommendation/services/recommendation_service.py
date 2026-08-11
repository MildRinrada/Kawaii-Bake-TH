"""Recommendation orchestration: gather facts, score, rank, diversify.

The pipeline (ADR 0018 §3):

1. candidate generation  the source app's public-listing fact selector,
   bounded by ``CANDIDATE_POOL_SIZE``;
2. eligibility  already inside step 1 (the anonymous public listing Q),
   plus exclusion of the viewer's own and already-engaged content;
3. feature extraction  bulk rating/favorite facts, one query each;
4–6. scoring, ranking, diversification  ``scoring_service`` pure functions;
7. pagination  at the API edge, over the ranked id list.

This service reads through other apps' public selectors only, and writes
nothing anywhere.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from django.utils import timezone

from apps.courses.selectors import course_selector, enrollment_selector
from apps.favorites.selectors import favorite_selector
from apps.recipes.selectors import recipe_selector
from apps.recommendation.constants import (
    CANDIDATE_POOL_SIZE,
    INTEREST_ENROLLMENT,
    INTEREST_FAVORITE,
    INTEREST_POSITIVE_REVIEW,
    INTEREST_PROFILE_CATEGORY,
    POSITIVE_REVIEW_MIN_RATING,
)
from apps.recommendation.services import scoring_service
from apps.recommendation.services.scoring_service import (
    EMPTY_CONTEXT,
    Candidate,
    ScoredCandidate,
    TasteContext,
)
from apps.reviews.selectors import rating_selector, review_selector
from apps.users.selectors import profile_selector


@dataclass(frozen=True)
class RecommendationItem:
    """One ranked result: the target and the evidence codes behind it."""

    target_id: int
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class _Signals:
    """The viewer's raw behavioral facts, gathered once per request."""

    experience_level: str
    profile_category_slugs: tuple[str, ...]
    favorited_recipe_ids: list[int]
    favorited_course_ids: list[int]
    positive_recipe_ids: list[int]
    positive_course_ids: list[int]
    reviewed_recipe_ids: list[int]
    reviewed_course_ids: list[int]
    enrolled_course_ids: list[int]
    recipe_facts: dict
    course_facts: dict


_NO_SIGNALS = _Signals(
    experience_level="",
    profile_category_slugs=(),
    favorited_recipe_ids=[],
    favorited_course_ids=[],
    positive_recipe_ids=[],
    positive_course_ids=[],
    reviewed_recipe_ids=[],
    reviewed_course_ids=[],
    enrolled_course_ids=[],
    recipe_facts={},
    course_facts={},
)


def _gather_signals(*, viewer_id: int | None) -> _Signals:
    """Collect the viewer's behavioral facts through public selectors.

    Anonymous viewers get the empty bundle at zero queries  cold start is
    the same pipeline with nothing to feed it.
    """
    if viewer_id is None:
        return _NO_SIGNALS

    fact = profile_selector.get_personalization_fact(user_id=viewer_id)
    favorited_recipes = favorite_selector.favorited_recipe_ids(user_id=viewer_id)
    favorited_courses = favorite_selector.favorited_course_ids(user_id=viewer_id)
    reviews = review_selector.review_facts_for_user(user_id=viewer_id)
    enrolled = list(enrollment_selector.list_enrolled_course_ids(user_id=viewer_id))

    positive_recipes = [
        r.recipe_id
        for r in reviews
        if r.recipe_id and r.rating >= POSITIVE_REVIEW_MIN_RATING
    ]
    positive_courses = [
        r.course_id
        for r in reviews
        if r.course_id and r.rating >= POSITIVE_REVIEW_MIN_RATING
    ]

    recipe_facts = recipe_selector.signal_facts(
        ids=sorted(set(favorited_recipes) | set(positive_recipes))
    )
    course_facts = course_selector.signal_facts(
        ids=sorted(set(favorited_courses) | set(positive_courses) | set(enrolled))
    )

    return _Signals(
        experience_level=fact.experience_level if fact else "",
        profile_category_slugs=fact.favorite_category_slugs if fact else (),
        favorited_recipe_ids=favorited_recipes,
        favorited_course_ids=favorited_courses,
        positive_recipe_ids=positive_recipes,
        positive_course_ids=positive_courses,
        reviewed_recipe_ids=[r.recipe_id for r in reviews if r.recipe_id],
        reviewed_course_ids=[r.course_id for r in reviews if r.course_id],
        enrolled_course_ids=enrolled,
        recipe_facts=recipe_facts,
        course_facts=course_facts,
    )


def _build_context(*, signals: _Signals, liked_creator_ids: frozenset[int]) -> TasteContext:
    """Turn raw signals into the scoring context.

    Interest in a category accumulates across every kind of evidence 
    a favorited bread recipe and an enrolled bread course both push
    ``bread`` up, weighted by evidence strength.
    """
    if signals is _NO_SIGNALS:
        return EMPTY_CONTEXT

    interest: dict[str, float] = {}
    favorite_slugs: set[str] = set()
    review_slugs: set[str] = set()
    course_slugs: set[str] = set()

    def _accumulate(slugs: tuple[str, ...], weight: float, bucket: set[str]) -> None:
        for slug in slugs:
            interest[slug] = interest.get(slug, 0.0) + weight
            bucket.add(slug)

    profile_slugs = set(signals.profile_category_slugs)
    for slug in profile_slugs:
        interest[slug] = interest.get(slug, 0.0) + INTEREST_PROFILE_CATEGORY

    for recipe_id in signals.favorited_recipe_ids:
        fact = signals.recipe_facts.get(recipe_id)
        if fact:
            _accumulate(fact.category_slugs, INTEREST_FAVORITE, favorite_slugs)
    for course_id in signals.favorited_course_ids:
        fact = signals.course_facts.get(course_id)
        if fact:
            _accumulate(fact.category_slugs, INTEREST_FAVORITE, favorite_slugs)

    for recipe_id in signals.positive_recipe_ids:
        fact = signals.recipe_facts.get(recipe_id)
        if fact:
            _accumulate(fact.category_slugs, INTEREST_POSITIVE_REVIEW, review_slugs)
    for course_id in signals.positive_course_ids:
        fact = signals.course_facts.get(course_id)
        if fact:
            _accumulate(fact.category_slugs, INTEREST_POSITIVE_REVIEW, review_slugs)

    for course_id in signals.enrolled_course_ids:
        fact = signals.course_facts.get(course_id)
        if fact:
            _accumulate(fact.category_slugs, INTEREST_ENROLLMENT, course_slugs)

    return TasteContext(
        interest_weights=interest,
        profile_category_slugs=frozenset(profile_slugs),
        favorite_category_slugs=frozenset(favorite_slugs),
        review_category_slugs=frozenset(review_slugs),
        course_category_slugs=frozenset(course_slugs),
        liked_creator_ids=liked_creator_ids,
        fit_difficulties=scoring_service.context_fit_difficulties(
            signals.experience_level
        ),
    )


def recommend_recipes(
    *, viewer_id: int | None, now: datetime | None = None
) -> list[RecommendationItem]:
    """Ranked recipe recommendations for a viewer.

    Excluded: the viewer's own recipes and everything they already
    favorited or reviewed  the feed surfaces new content, not a mirror of
    their history (ADR 0018 §3).

    Args:
        viewer_id: Primary key of the viewer, or ``None`` for cold start.
        now: Reference time for recency; injected by tests, defaulted here.

    Returns:
        Ranked, diversified items  ids and reason codes only.
    """
    return [
        RecommendationItem(target_id=item.id, reasons=item.reasons)
        for item in _recipe_pipeline(viewer_id=viewer_id, now=now)
    ]


def _recipe_pipeline(
    *, viewer_id: int | None, now: datetime | None = None
) -> list[ScoredCandidate]:
    """The full recipe pipeline, scores still attached (internal seam)."""
    now = now or timezone.now()
    signals = _gather_signals(viewer_id=viewer_id)
    liked_creators = frozenset(
        fact.author_id
        for recipe_id, fact in signals.recipe_facts.items()
        if recipe_id
        in set(signals.favorited_recipe_ids) | set(signals.positive_recipe_ids)
    )
    context = _build_context(signals=signals, liked_creator_ids=liked_creators)

    excluded = set(signals.favorited_recipe_ids) | set(signals.reviewed_recipe_ids)
    candidates = [
        Candidate(
            id=fact.id,
            creator_id=fact.author_id,
            difficulty=fact.difficulty,
            published_at=fact.published_at,
            category_slugs=fact.category_slugs,
        )
        for fact in recipe_selector.public_candidate_facts(limit=CANDIDATE_POOL_SIZE)
        if fact.id not in excluded and fact.author_id != viewer_id
    ]
    ids = [candidate.id for candidate in candidates]
    ratings = rating_selector.facts_for_recipes(ids=ids)
    favorite_counts = favorite_selector.favorite_counts_for_recipes(ids=ids)
    return _score_and_rank(
        candidates=candidates,
        context=context,
        ratings=ratings,
        favorite_counts=favorite_counts,
        now=now,
    )


def recommend_courses(
    *, viewer_id: int | None, now: datetime | None = None
) -> list[RecommendationItem]:
    """Ranked course recommendations for a viewer.

    Excluded: the viewer's own courses and everything they already enrolled
    in (active **or** completed  a finished course is history, not a
    suggestion), favorited or reviewed.

    Args:
        viewer_id: Primary key of the viewer, or ``None`` for cold start.
        now: Reference time for recency; injected by tests, defaulted here.

    Returns:
        Ranked, diversified items  ids and reason codes only.
    """
    return [
        RecommendationItem(target_id=item.id, reasons=item.reasons)
        for item in _course_pipeline(viewer_id=viewer_id, now=now)
    ]


def _course_pipeline(
    *, viewer_id: int | None, now: datetime | None = None
) -> list[ScoredCandidate]:
    """The full course pipeline, scores still attached (internal seam)."""
    now = now or timezone.now()
    signals = _gather_signals(viewer_id=viewer_id)
    liked_creators = frozenset(
        fact.instructor_id
        for course_id, fact in signals.course_facts.items()
        if course_id
        in set(signals.favorited_course_ids) | set(signals.positive_course_ids)
    )
    context = _build_context(signals=signals, liked_creator_ids=liked_creators)

    excluded = (
        set(signals.enrolled_course_ids)
        | set(signals.favorited_course_ids)
        | set(signals.reviewed_course_ids)
    )
    candidates = [
        Candidate(
            id=fact.id,
            creator_id=fact.instructor_id,
            difficulty=fact.difficulty,
            published_at=fact.published_at,
            category_slugs=fact.category_slugs,
        )
        for fact in course_selector.public_candidate_facts(limit=CANDIDATE_POOL_SIZE)
        if fact.id not in excluded and fact.instructor_id != viewer_id
    ]
    ids = [candidate.id for candidate in candidates]
    ratings = rating_selector.facts_for_courses(ids=ids)
    favorite_counts = favorite_selector.favorite_counts_for_courses(ids=ids)
    return _score_and_rank(
        candidates=candidates,
        context=context,
        ratings=ratings,
        favorite_counts=favorite_counts,
        now=now,
    )


def _score_and_rank(
    *,
    candidates: list[Candidate],
    context: TasteContext,
    ratings: dict,
    favorite_counts: dict,
    now: datetime,
) -> list[ScoredCandidate]:
    """Steps 4–6 of the pipeline over an already-eligible candidate list.

    Returns the ordered :class:`ScoredCandidate` rows with their scores
    still attached; the public feed functions strip the score at their
    boundary (ADR 0018 §14), while the staff preview keeps it.
    """
    seen: set[int] = set()
    scored = []
    for candidate in candidates:
        if candidate.id in seen:
            continue
        seen.add(candidate.id)
        rating = ratings.get(candidate.id)
        scored.append(
            scoring_service.score_candidate(
                candidate=candidate,
                context=context,
                rating_average=rating.average if rating else 0.0,
                rating_count=rating.count if rating else 0,
                favorite_count=favorite_counts.get(candidate.id, 0),
                now=now,
            )
        )
    return scoring_service.diversify(scoring_service.rank(scored))


def preview_scored(
    *, kind: str, target_user_id: int, now: datetime | None = None
) -> list[ScoredCandidate]:
    """The pipeline as one user would see it, scores included - staff only.

    ADR 0028 amends ADR 0018 §10 for exactly this seam: the public feed
    still never carries a score, but an operator debugging "why was this
    recommended?" may see the ranked list with its numbers. The output
    stays aggregate - scores and reason codes, never the target user's
    raw history.

    Args:
        kind: ``recipes`` or ``courses``.
        target_user_id: The user whose feed to reproduce.
        now: Reference time for recency; defaults to the real clock.

    Returns:
        The ranked, diversified candidates with scores attached.
    """
    if kind == "courses":
        return _course_pipeline(viewer_id=target_user_id, now=now)
    return _recipe_pipeline(viewer_id=target_user_id, now=now)
