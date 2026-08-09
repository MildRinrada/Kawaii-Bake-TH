# 0021 — Course list search and stored aggregates (duration, rating)

- **Status:** Accepted
- **Date:** 2026-08-08
- **Phase:** Course discovery enhancement (frontend `/courses` + backend)

## Context

The `/courses` page was rebuilt as a discovery surface. Three capabilities were
missing from the API and were being worked around on the client:

1. **No `search` parameter** — the frontend downloaded the whole catalog and
   filtered client-side.
2. **No course length on the list card** — lesson durations exist only in the
   lessons app; showing a total required per-course syllabus fetches (N+1).
3. **No rating on the list card** — `/courses/{slug}/rating/` exists per
   target only; showing stars on a grid meant one request per card (N+1).

Two architectural constraints shape any fix:

- **Dependency direction** (ADR 0009): `lessons → courses` and
  `reviews → courses`. Courses is a leaf; it may never import, join, or count
  another app's rows — including through reverse accessors.
- **The counter rule** (Database.md): no stored aggregates without proven
  need *and* a rebuild strategy. `Course.published_lesson_count` is the
  existing sanctioned example.

## Decision

### 1. `?search=` on `GET /courses/`

Validated by the strict query serializer (max 100 chars), applied in the
selector as `icontains` over **title, summary, description**. Recipes search
covers title+summary only; courses add description because course descriptions
carry the technique vocabulary users search for and the catalog is small.
Hidden/draft courses stay invisible — search composes with the existing
visibility Q, and tests pin that.

### 2. `Course.published_duration_minutes`

Same pattern, same choke point, same command as the lesson counter:
`lesson_repository._sync_counter` now pushes `(count, duration_sum)` in one
aggregate query through the extended public API
`course_service.sync_published_lesson_count(..., duration_minutes=)` — the new
argument is optional so the contract change is additive. `manage.py
recount_lessons` rebuilds both.

### 3. `Course.rating_average` / `Course.rating_count`

This **supersedes, for courses only**, the Phase 6 note that rating statistics
are "computed, never stored". That note's condition — "counters nothing else
maintains" — no longer holds:

- **Proven need:** the course list must carry a rating without an N+1, and
  courses cannot compute it (would invert `reviews → courses`).
- **Maintainer:** `review_repository` is the single mutation choke point for
  reviews. Every create / rating edit / moderation / soft-delete of a
  course-targeted review recomputes the active-review aggregate and pushes it
  through the new public API `course_service.sync_rating_aggregate()` inside
  the same transaction.
- **Rebuild strategy:** `manage.py rebuild_rating_aggregates` recomputes every
  reviewed course and resets stale rows.

The per-target `/rating/` endpoint (with star distribution) remains computed
on read; recipes remain compute-on-read entirely (their list has no rating —
unchanged, revisit only with the same proven need).

`rating_average` is `DecimalField(3,2)`, null when unreviewed — the serializer
emits `null`, never a fake `0.0`.

### 4. Serializer additions

`CourseListItemSerializer` gains `total_duration_minutes`, `rating_average`,
`rating_count` — all read from columns on the row. The list query count is
unchanged (the existing `assertNumQueries` pin still passes).

## Consequences

- Course cards show length and rating from a single list request.
- Two more rebuildable caches exist; both have drift tests (a factory that
  bypasses the choke point, then the command repairing it).
- The reviews factory writes at the model layer and therefore does **not**
  maintain aggregates — tests that assert aggregates must go through the
  service/repository, which is also true of production code paths.
- Frontend `/courses` moved back to server-side search + filters and reads
  the new fields; the featured-course rating no longer needs its own request.

## Alternatives rejected

- **Annotating rating/duration in the courses selector** — requires joining
  other apps' tables from courses; inverts the dependency direction.
- **View-level stitching** (the favorites pattern) — the stitcher must import
  both sides; for `courses` list that means `courses → reviews`, a cycle.
- **Computing on the frontend** — the N+1 this ADR exists to remove.
