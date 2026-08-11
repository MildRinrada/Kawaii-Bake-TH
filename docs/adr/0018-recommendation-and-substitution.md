# ADR 0018  Recommendation and Ingredient Substitution

**Status:** Accepted (Phase 12)
**Context:** Phase 12 adds `apps/recommendation`: deterministic recipe and
course recommendation feeds, and a per-recipe ingredient substitution
endpoint backed by an in-code rule registry. Machine learning, a stored
recommendation state, and an ingredient catalogue are explicitly out of
scope.

---

## 1. Recommendation is a pure consumer

The app owns **zero tables and zero facts**. Everything it returns is
derived, per request, from facts other domains own, read through their
public selectors:

```
recipes ────▶ recommendation   (public candidate facts, signal facts)
courses ────▶ recommendation   (public candidate facts, signal facts, enrollments)
favorites ──▶ recommendation   (the user's favorites, favorite counts)
reviews ────▶ recommendation   (the user's review facts, rating aggregates)
users ──────▶ recommendation   (profile favorite categories, experience level)
```

No source domain imports recommendation, and recommendation writes nothing
back. Deleting the app touches nothing else  the gamification
reversibility goal (ADR 0015 §1) applies verbatim.

## 2. Source-domain ownership

Every fact used in scoring stayed where it lives. The additive-public-
selector mechanism from Phase 9 carried the whole phase: `recipes` and
`courses` gained candidate/signal fact selectors, `favorites` gained id
lists and live counts, `reviews` gained per-user facts and a bulk rating
aggregate, `users` gained a `PersonalizationFact`. Each returns plain
dataclasses or dicts  never models. The two quiz/lesson signals the spec
lists as optional were **not** wired: their taste information (categories
of courses the user studies) is already captured by the enrollment signal,
so adding selectors to two more apps would widen the surface without
changing a single ranking. Reduced feature, not fabricated data.

## 3. Candidate generation

Candidates are the newest `CANDIDATE_POOL_SIZE` (200) publicly listed
items, fetched by the source app's own fact selector as a LIMIT-ed values
query  never the whole table, and never model instances. Eligibility is
decided *inside* that selector by the **anonymous public listing Q** (§7).
The pipeline then drops the viewer's own content and everything they
already engaged with: favorited or reviewed recipes; enrolled (active
**or completed**  a finished course is history, not a suggestion),
favorited or reviewed courses. A dropped enrollment returns the course to
the feed. The feed surfaces new content, not a mirror of the user's
history.

## 4. Scoring

`scoring_service.score_candidate` is a pure function: additive weighted
features (category-interest match, creator affinity, rating average,
capped rating/favorite counts, linear recency decay, difficulty-fit
against the profile's experience level), every weight a named constant in
`constants.py`  changing ranking policy is a reviewable one-file diff,
the `XP_RULES` precedent. Interest per category accumulates across
evidence kinds (profile choice 2.0, favorite 1.0, positive review ≥4 
1.0, enrollment 1.0) and is capped so one obsession cannot drown the
other features.

## 5. Ranking

`rank()` sorts by score descending with **id ascending as the tie-break**
 total, deterministic order with no dependence on database return order.
Duplicates are structurally impossible (candidates come from a pk query;
a belt-and-braces `seen` set guards the pipeline anyway).

## 6. Cold start

Cold start is **not a separate code path**: an anonymous or history-less
viewer gets the `EMPTY_CONTEXT`, under which the personal features
contribute zero and scoring degrades to the global ones  rating,
favorite counts, recency. A test pins that a brand-new user's feed equals
the anonymous feed. No hardcoded ids, no random ordering, deterministic
by construction.

## 7. Visibility

The candidate selectors apply each source app's own `visible_in_list_q()`
with **no viewer at all**  deliberately stricter than the viewer's own
rights. A recommendation feed is a broadcast surface: unlisted content is
reachable-by-link, not listable, and private/draft/archived content is
neither  so none of them may appear even for staff, and the rule that
decides this is the source app's single Q builder, not a re-implementation
that could drift. Signal extraction (categories of the user's own
favorites) is intentionally not visibility-filtered: it reads the user's
own history as aggregate evidence and is never serialized (§10).

## 8. Deterministic behavior

Same facts → same feed, always: no randomness anywhere, `now` is a
parameter of the scoring pipeline (defaulted at the service edge, injected
by tests), ties break on id, reason codes render in a fixed declared
order, and diversification is a greedy algorithm with a deterministic
tie-break. Tests call the pipeline twice and assert equality.

## 9. Why there is no recommendation table

Source facts change on every favorite, review, enrollment and publish; a
stored recommendation is stale the moment it is written and needs
invalidation machinery nothing else in the project has. Computing per
request costs a bounded, flat query count (4 anonymous, 11 with full
history  pinned by `assertNumQueries`). `recommendation_history`,
`recommendation_score`, `user_interest`, `ingredient` and
`ingredient_alias` were all considered and rejected  nothing in the
architecture requires them. If caching ever becomes necessary it wraps
the service behind `infrastructure/cache`, invisible to every caller.

## 10. Personalization privacy

The response exposes exactly two things per item: the public card (the
content app's own list serializer  the favorites stitching pattern) and
**aggregate reason codes** (`matches_your_favorite_categories`,
`similar_to_your_favorites`, …). Reasons are derived from the same
evidence as the score, so they can never claim unused evidence  and none
of them name a specific behavioral event. Raw history, numeric scores,
feature values and emails never appear; scores and weights are not client
inputs either.

## 11. Ingredient normalization

Substitution matching runs on the exact normalisation `recipes` already
stores in `RecipeIngredient.normalized_name` (NFC, casefold, whitespace
collapse  Thai-safe). The implementation moved from `apps.recipes.utils`
to `apps.common.utils.text` (re-exported for existing callers) the moment
a second app needed it  the established `build_upload_path` precedent 
because two implementations of one matching rule would drift, which is
the exact failure the normalized column exists to prevent.

## 12. Substitution rule ownership

`rules/substitution_rules.py` owns substitution knowledge: canonical
rules keyed by normalised names, an alias map folding Thai and English
spellings onto one rule, and a `lookup()` seam. Honesty is part of the
contract: a ratio appears only where the conversion is established
kitchen practice; confidence is three coarse buckets (`high/medium/low`)
because that is all the precision that honestly exists; allergen
implications are cautions in notes, and nothing claims nutritional
equivalence, allergy safety or medical suitability. A registry test
asserts every key and alias is already in normalised form, so a typo
cannot silently create an unreachable rule. An ingredient the registry
does not know returns an honest empty list  never a guess.

## 13. Why no ML in this phase

A model would demand training data the platform does not have yet,
an evaluation loop nothing can run, and non-deterministic output that
breaks the testing discipline every phase relies on. Deterministic
content/behavior scoring is explainable to users (§10), testable to the
exact ordering, and tunable by editing named constants. It also produces
the interaction logs a future model would train on.

## 14. Future ML seam

The seam is the service boundary: `recommend_recipes`/`recommend_courses`
return `RecommendationItem(target_id, reasons)`. A learned ranker
replaces the middle of the pipeline (scoring/ranking) behind the same
signature; candidates, eligibility, privacy and the API contract are
untouched. The provider-factory pattern (`ai/`, ADR 0013) is the model
for how an external inference service would plug in.

## 15. Future ingredient catalogue seam

`RecipeIngredient`'s own docstring (Phase 2) already plans the catalogue:
a nullable FK backfilled by grouping on `normalized_name`. When it
arrives, the rule registry's `lookup()` becomes a catalogue query behind
the same signature, and the alias map becomes catalogue alias rows. The
substitution API shape does not change.

## 16. Performance limitations

The pool is the newest 200 public items  content older than the pool
never surfaces, which is acceptable for a feed and is the declared
trade-off of ranking in application code. Query counts are flat and
pinned (recommendations: 4/11 + 2 card queries per page; substitution: 2).
When the catalogue grows past what a LIMIT-ed newest-first pool serves
well, candidate generation moves behind the search-backend seam
(`infrastructure/search`)  the same upgrade path recipes' own listing
search already declares.
