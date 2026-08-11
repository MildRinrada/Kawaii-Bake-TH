"""Pure scoring, ranking and diversification  plus rule-registry integrity."""

from __future__ import annotations

from datetime import datetime, timedelta

from django.test import SimpleTestCase

from apps.common.utils.text import normalize_ingredient_name
from apps.recommendation.constants import (
    CATEGORY_SCORE_CAP,
    CONFIDENCE_HIGH,
    CONFIDENCE_LOW,
    CONFIDENCE_MEDIUM,
    REASON_AUTHOR_AFFINITY,
    REASON_HIGHLY_RATED,
    REASON_NEW,
    REASON_ORDER,
    REASON_POPULAR,
    REASON_PROFILE_CATEGORY,
    RECENCY_WINDOW_DAYS,
    W_CATEGORY_MATCH,
)
from apps.recommendation.rules import substitution_rules
from apps.recommendation.services import scoring_service
from apps.recommendation.services.scoring_service import (
    EMPTY_CONTEXT,
    Candidate,
    ScoredCandidate,
    TasteContext,
)

# `fromisoformat` rather than `tzinfo=UTC`: the dev interpreter is 3.10
# while ruff targets py312, and `datetime.UTC` exists only from 3.11.
NOW = datetime.fromisoformat("2026-08-01T00:00:00+00:00")
OLD = NOW - timedelta(days=RECENCY_WINDOW_DAYS + 10)


def make_candidate(**kwargs) -> Candidate:
    defaults = {
        "id": 1,
        "creator_id": 100,
        "difficulty": "easy",
        "published_at": OLD,
        "category_slugs": (),
    }
    defaults.update(kwargs)
    return Candidate(**defaults)


def score(candidate: Candidate, context: TasteContext = EMPTY_CONTEXT, **kwargs) -> ScoredCandidate:
    defaults = {"rating_average": 0.0, "rating_count": 0, "favorite_count": 0, "now": NOW}
    defaults.update(kwargs)
    return scoring_service.score_candidate(candidate=candidate, context=context, **defaults)


class ScoringTests(SimpleTestCase):
    """score_candidate is a deterministic, explainable function."""

    def test_same_input_same_score(self) -> None:
        candidate = make_candidate(category_slugs=("bread",))
        context = TasteContext(interest_weights={"bread": 2.0})
        first = score(candidate, context, rating_average=4.5, rating_count=10)
        second = score(candidate, context, rating_average=4.5, rating_count=10)
        self.assertEqual(first, second)

    def test_category_interest_raises_score(self) -> None:
        context = TasteContext(interest_weights={"bread": 2.0})
        matching = score(make_candidate(category_slugs=("bread",)), context)
        other = score(make_candidate(id=2, category_slugs=("cake",)), context)
        self.assertGreater(matching.score, other.score)

    def test_category_interest_is_capped(self) -> None:
        context = TasteContext(interest_weights={"bread": 999.0})
        item = score(make_candidate(category_slugs=("bread",)), context)
        self.assertEqual(item.score, W_CATEGORY_MATCH * CATEGORY_SCORE_CAP)

    def test_author_affinity_raises_score_and_reason(self) -> None:
        context = TasteContext(liked_creator_ids=frozenset({100}))
        liked = score(make_candidate(), context)
        stranger = score(make_candidate(id=2, creator_id=200), context)
        self.assertGreater(liked.score, stranger.score)
        self.assertIn(REASON_AUTHOR_AFFINITY, liked.reasons)
        self.assertNotIn(REASON_AUTHOR_AFFINITY, stranger.reasons)

    def test_rating_raises_score(self) -> None:
        rated = score(make_candidate(), rating_average=5.0, rating_count=5)
        unrated = score(make_candidate(id=2))
        self.assertGreater(rated.score, unrated.score)

    def test_rating_count_is_capped(self) -> None:
        at_cap = score(make_candidate(), rating_average=4.0, rating_count=20)
        over_cap = score(make_candidate(id=2), rating_average=4.0, rating_count=5000)
        self.assertEqual(at_cap.score, over_cap.score)

    def test_favorite_count_is_capped(self) -> None:
        at_cap = score(make_candidate(), favorite_count=20)
        over_cap = score(make_candidate(id=2), favorite_count=5000)
        self.assertEqual(at_cap.score, over_cap.score)

    def test_recent_beats_old_all_else_equal(self) -> None:
        fresh = score(make_candidate(published_at=NOW - timedelta(days=1)))
        stale = score(make_candidate(id=2, published_at=OLD))
        self.assertGreater(fresh.score, stale.score)
        self.assertIn(REASON_NEW, fresh.reasons)
        self.assertNotIn(REASON_NEW, stale.reasons)

    def test_no_recency_bonus_outside_window(self) -> None:
        stale = score(make_candidate(published_at=OLD))
        self.assertEqual(stale.score, 0.0)

    def test_difficulty_fit_bonus(self) -> None:
        context = TasteContext(fit_difficulties=frozenset({"easy"}))
        fitting = score(make_candidate(difficulty="easy"), context)
        hard = score(make_candidate(id=2, difficulty="expert"), context)
        self.assertGreater(fitting.score, hard.score)

    def test_reasons_require_evidence(self) -> None:
        item = score(make_candidate())
        self.assertEqual(item.reasons, ())

    def test_global_reasons_from_thresholds(self) -> None:
        item = score(
            make_candidate(), rating_average=4.5, rating_count=3, favorite_count=3
        )
        self.assertIn(REASON_HIGHLY_RATED, item.reasons)
        self.assertIn(REASON_POPULAR, item.reasons)

    def test_reasons_follow_fixed_order(self) -> None:
        context = TasteContext(
            interest_weights={"bread": 2.0},
            profile_category_slugs=frozenset({"bread"}),
            liked_creator_ids=frozenset({100}),
        )
        item = score(
            make_candidate(category_slugs=("bread",), published_at=NOW),
            context,
            rating_average=5.0,
            rating_count=10,
            favorite_count=10,
        )
        expected = tuple(code for code in REASON_ORDER if code in set(item.reasons))
        self.assertEqual(item.reasons, expected)
        self.assertEqual(item.reasons[0], REASON_PROFILE_CATEGORY)


class RankingTests(SimpleTestCase):
    """rank() and diversify() are deterministic re-orderings."""

    @staticmethod
    def scored(id: int, score: float, category: str = "") -> ScoredCandidate:
        return ScoredCandidate(id=id, score=score, reasons=(), primary_category=category)

    def test_rank_orders_by_score(self) -> None:
        ranked = scoring_service.rank(
            [self.scored(1, 1.0), self.scored(2, 5.0), self.scored(3, 3.0)]
        )
        self.assertEqual([item.id for item in ranked], [2, 3, 1])

    def test_rank_breaks_ties_by_id(self) -> None:
        ranked = scoring_service.rank(
            [self.scored(9, 2.0), self.scored(3, 2.0), self.scored(5, 2.0)]
        )
        self.assertEqual([item.id for item in ranked], [3, 5, 9])

    def test_diversify_is_deterministic(self) -> None:
        ranked = scoring_service.rank(
            [
                self.scored(1, 5.0, "bread"),
                self.scored(2, 4.9, "bread"),
                self.scored(3, 4.8, "cake"),
                self.scored(4, 4.7, "bread"),
            ]
        )
        first = scoring_service.diversify(list(ranked))
        second = scoring_service.diversify(list(ranked))
        self.assertEqual(first, second)

    def test_diversify_spreads_near_ties_across_categories(self) -> None:
        ranked = scoring_service.rank(
            [
                self.scored(1, 5.0, "bread"),
                self.scored(2, 4.9, "bread"),
                self.scored(3, 4.8, "cake"),
            ]
        )
        ordered = scoring_service.diversify(ranked)
        # After bread leads, the cake near-tie overtakes the second bread.
        self.assertEqual([item.id for item in ordered], [1, 3, 2])

    def test_diversify_never_promotes_clearly_weaker(self) -> None:
        ranked = scoring_service.rank(
            [
                self.scored(1, 10.0, "bread"),
                self.scored(2, 9.0, "bread"),
                self.scored(3, 1.0, "cake"),
            ]
        )
        ordered = scoring_service.diversify(ranked)
        self.assertEqual([item.id for item in ordered], [1, 2, 3])

    def test_diversify_preserves_membership(self) -> None:
        ranked = scoring_service.rank(
            [self.scored(i, float(i), "bread" if i % 2 else "cake") for i in range(1, 8)]
        )
        ordered = scoring_service.diversify(ranked)
        self.assertEqual(
            sorted(item.id for item in ordered), sorted(item.id for item in ranked)
        )


class SubstitutionRegistryTests(SimpleTestCase):
    """The registry cannot silently hold unreachable or dishonest rules."""

    def test_rule_keys_are_normalized(self) -> None:
        for key in substitution_rules.RULES:
            self.assertEqual(key, normalize_ingredient_name(key))

    def test_alias_keys_are_normalized_and_targets_exist(self) -> None:
        for alias, target in substitution_rules.ALIASES.items():
            self.assertEqual(alias, normalize_ingredient_name(alias))
            self.assertIn(target, substitution_rules.RULES)

    def test_options_use_coarse_confidence_only(self) -> None:
        allowed = {CONFIDENCE_HIGH, CONFIDENCE_MEDIUM, CONFIDENCE_LOW}
        for options in substitution_rules.RULES.values():
            self.assertTrue(options)
            for option in options:
                self.assertIn(option.confidence, allowed)
                self.assertTrue(option.name)

    def test_lookup_resolves_aliases(self) -> None:
        direct = substitution_rules.lookup("เนย")
        via_alias = substitution_rules.lookup("butter")
        self.assertEqual(direct, via_alias)
        self.assertTrue(direct)

    def test_lookup_unknown_is_empty(self) -> None:
        self.assertEqual(substitution_rules.lookup("ผงชูรส"), ())
