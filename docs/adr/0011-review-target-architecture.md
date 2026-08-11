# 0011  Review target architecture

**Status:** Accepted (Phase 5)

## Context

Phase 5 adds user interaction: reviews (rating + comment) and favorites, both
targeting **two** content types  recipes and courses. One model must point at
"a recipe or a course", which forces the classic choice: Django's
`GenericForeignKey` (contenttypes) or explicit per-target relations.

## Decision 1  Explicit nullable FKs, not GenericForeignKey

`Review` and `Favorite` each carry `recipe` and `course` as nullable FKs with
a check constraint enforcing **exactly one** set.

Why GFK loses on every axis this project cares about:

- **Integrity.** A GFK is two loose columns the database cannot verify: no FK
  constraint, no CASCADE, orphans accumulate silently. Explicit FKs give real
  referential integrity and real cascade semantics for free.
- **The visibility mechanism.** The whole codebase enforces read access
  through prefix-parameterised `Q` builders composed across **real joins**
  (`recipe__status`, `course__enrollments__…`  ADR 0009 mechanism #2). A GFK
  cannot be joined, so every visibility check would become a second,
  hand-rolled implementation  exactly the drift the Q builders exist to
  prevent. This argument alone is decisive.
- **Constraints.** "One active review per user per target" is a partial
  unique index on `(user, recipe) WHERE status='active'`. No equivalent
  exists over a `(content_type, object_id)` pair without fragile expression
  indexes.
- **Performance.** Statistics are one indexed aggregate per target
  (`reviews_recipe_idx`); GFK aggregates filter on two columns with no FK
  index semantics and can prefetch only via `prefetch_related` gymnastics.
- **API clarity.** OpenAPI types stay concrete (`recipe_slug` / nested
  cards), not `content_type: int, object_id: int`.

Cost accepted: each new reviewable type is one nullable column plus updated
constraints. Target types are few, known, and added deliberately  a schema
migration per type is the *right* amount of friction, not a limitation. If
targets ever became open-ended (dozens of types), that would be a different
system and a new ADR.

The same shape serves both models; `Favorite` differs only in having no
status  a favorite is a toggle, so unfavoriting hard-deletes the row.
Longitudinal "favorite history" for analytics belongs to a future event
stream, not to soft-deleted toggle rows.

## Decision 2  Why reviews imports no recipe/course models

`reviews` and `favorites` are dependent-side apps (ADR 0008): their FKs are
lazy string references, target resolution goes through the content apps'
public ref selectors (`get_recipe_ref`  added in Phase 5 as the mirror of
`get_course_ref`  and `get_course_ref`), and list filtering composes the
exported visibility Q builders. Phase 5 additions to the content apps were
all additive public API: a `prefix` parameter on the recipes Q builders,
`RecipeRef`, and `list_viewable_by_ids` on both apps (the detail-rule batch
fetch that keeps the favorites list and its cards under one rule).

Consequences that fall out of composing the existing rules rather than
writing new ones:

- a favorited recipe that goes private **silently leaves** its owner's list
  and returns if the recipe does  the row is never deleted;
- an archived course stays in an enrolled student's favorites, because the
  courses detail rule already has that branch;
- hidden targets cannot be reviewed, rated, favorited **or unfavorited** 
  fail-closed everywhere, hidden and absent identical.

## Decision 3  Statistics are computed, never stored

`rating_selector` aggregates average, count and star distribution in one
query over `ACTIVE` rows. There are no `rating_average`/`review_count`
columns  Database.md's "counters deliberately not added" section now has its
consumer, and the decision holds: a counter pinned to a moderation-sensitive
aggregate (hidden reviews leave the stats instantly) would need recomputation
hooks in every moderation path. The selector is the **caching seam**: wrap it
with the `infrastructure/cache` adapter keyed by target id, invalidated on
review writes, with zero caller changes. `popular` orderings gain a real
signal the day they want it by aggregating at query time or adding a
rebuildable counter then (ADR 0009 mechanism #1), when something exists to
maintain it.

## Decision 4  Review lifecycle and moderation

`status ∈ active / hidden / deleted`; nothing is ever hard-deleted. The
duplicate rule binds **active rows only**, so soft-deleting frees the slot
while keeping history  and re-reviewing creates a new row, preserving the
old text for audit. `hidden` is the moderation state (staff-only, via the
same PATCH endpoint  403, not 404, because the caller already addressed the
review legitimately); deleted rows are unaddressable by everyone including
staff (admin site reads them). Self-reviews are rejected (`own_content`):
creators must not inflate the averages ranking and recommendation will
consume.

**Known gap, recorded:** a user whose review was *hidden* can post a fresh
active review (the partial unique only sees active rows). Acceptable now;
future moderation work can extend the duplicate check to hidden rows.

## Future data these tables already serve

Ratings (1–5, timestamped, per user per target) and favorites (timestamped
toggles) are the classic interaction matrix: recommendation
(user × item affinity), ranking (`-favorite_count`, Bayesian average),
personalization and analytics all read these rows as-is. `list_by_ids` /
`list_viewable_by_ids` on the content apps are the prepared hydration path.
