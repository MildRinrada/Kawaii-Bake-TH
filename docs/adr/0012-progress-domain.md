# 0012 — The progress domain

**Status:** Accepted (Phase 6). Amends ADR 0009's placement of learner state.

## Context

Phase 3 put `LessonProgress` inside `apps/lessons` because lessons were its
only consumer. Phase 6 makes learner progress a growth point — streaks, XP,
achievements, dashboards — and none of that is lesson *content*. Keeping it
in `lessons` would either bloat that app with gamification concerns or force
future apps to import lesson internals.

## Decision 1 — Progress owns completion state; content apps know nothing

`apps/progress` owns `LessonProgress` (moved), `CourseProgress` (new) and
`LearningActivity` (new). The dependency edge is one-way:

```
progress ──▶ lessons ──▶ courses
    └────────────────────▶ courses (enrollment gate, completion recording)
```

Neither `lessons` nor `courses` imports `progress` — the syllabus lost its
progress merge (learner state now comes only from progress endpoints), and
the `{id}/complete/`, `{slug}/progress/` and `/me/progress/` routes are
progress-app urlconfs mounted under the content prefixes by config (the
ADR 0009 mounting precedent). Cross-app reads go through refs: Phase 6 added
`LessonRef` / `get_lesson_ref` / `list_published_refs` to lessons' public
selector API, mirroring `CourseRef`/`RecipeRef`.

What did **not** move: `Enrollment.completed_at` stays in courses.
Enrollment is *membership* state (courses' domain, referenced by re-enroll
restore); `CourseProgress.completed_at` is *learning* state (this domain's
derived fact). Progress computes, then tells courses through the existing
public API (`record_course_completion`) — the Phase 3 contract, unchanged,
now with a different caller.

## Decision 2 — Completion is a timestamp, not a boolean

`completed_at IS NULL` *is* the not-completed state — one field is both flag
and "when", and the two can never disagree (the Phase 3 model carried
`completed` + `completed_at` separately, one drift-capable pair).
`first_completed_at` is stamped once and survives un-completing: history
XP and certificates will reference, the `published_at` pattern.
`last_viewed_at` is the resume/watch-position hook, written on every
completion change now, by a player later. (`progress_percent` from Phase 3
was dropped — it had no writer besides complete/un-complete and its job is
`last_viewed_at`'s future.)

## Decision 3 — Counters are calculated, not stored

There is no `completed_lessons` column anywhere. Aggregates come from
`LessonProgress` rows at read time — one grouped query serves the whole
`/me/progress/` overview (flat query count, enforced by `assertNumQueries`).
A stored counter would need decrementing on un-complete, adjusting on lesson
delete, and reconciling on republish — three drift paths for one saved
query. `total_lessons` reads `Course.published_lesson_count`, the counter
lessons already maintains (ADR 0009) — reused, not duplicated.

## Decision 4 — CourseProgress is derived from LessonProgress

`recalculate_course_progress()` is the **only** writer: it aggregates this
domain's rows against the lessons app's published set and stamps
`CourseProgress.completed_at` via conditional UPDATE
(`WHERE completed_at IS NULL`) — once, ever. Required lessons = published
lessons; drafts never count, so adding an optional (draft) lesson cannot
break completion, and adding a published lesson later never un-stamps
(never-downgrade, Phase 3 rule preserved). The Phase 3 race mechanism
carries over whole: **write-through** (completing write recalculates) plus
**self-healing read** (the progress report recalculates at 100%), both
funneling through the same function.

## Decision 5 — Activity events are separate from progress state

`LearningActivity` is append-only facts ("user learned on date X"), distinct
from mutable state: un-completing a lesson must not retroactively break a
streak — what you did on Tuesday happened, however you later tidy your
checklist. The `(user, date, type)` unique makes daily recording idempotent,
which is the entire streak substrate; streak computation, XP and
leaderboards are future readers, not columns here.

**Recorded constraint:** only `lesson_completed` is wired. `quiz_completed`
and `recipe_created` exist as choices, but wiring them means quizzes/recipes
calling progress — and `quizzes ← progress ← lessons ← quizzes` would cycle.
Producers of those events will need either a dependency-free event mechanism
or a progress module split; that is a future phase's ADR.

## Consequences

- **Breaking API changes** (accepted, spec-mandated): the syllabus no longer
  carries `completed`/`progress_percent`; the complete endpoint returns
  `{lesson_id, completed, completed_at, first_completed_at,
  course_completed}`; the progress report's `completed_at` is now course
  completion (was enrollment's) and per-lesson rows gained
  `first_completed_at`.
- No data migration ships: the project is pre-deployment (every environment
  rebuilds from migrations). A production migration would need a cross-app
  copy step — noted, not needed.
- Old lessons progress tests were ported to `apps/progress/tests` with every
  behaviour assertion preserved.
