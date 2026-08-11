# 0009  The Courses ↔ Lessons Boundary

- **Status:** Accepted
- **Date:** 2026-08-07
- **Extends:** [ADR 0008](0008-cross-app-model-references.md)

## Context

Phase 3 splits the learning domain across two apps: `courses` (structure,
metadata, enrollment, lifecycle) and `lessons` (content, ordering, progress,
completion). The flows are deeply entangled  a course cannot publish without
lessons, lesson visibility depends on course visibility and enrollment, and
finishing every lesson completes the course  yet the requirement "do not put
lesson progress logic inside courses" demands a hard boundary.

## Decision

**Dependency direction: `lessons → courses`, strictly one way.** `Lesson.course`
is a lazy string FK (ADR 0008); `courses` never imports `lessons` and never
touches the `course.lessons` reverse accessor, so it stays shippable alone.

Four mechanisms make the entangled flows work without breaking that direction:

### 1. The publish gate reads a counter courses owns

`Course.published_lesson_count` is a column on courses' own table, pushed by
lessons calling `course_service.sync_published_lesson_count()` inside the same
transaction as every lesson mutation. `assert_publishable` reads its own
column; it counts nothing of lessons'. The counter is a **rebuildable cache**
with a benign failure mode  the distinction ADR-era discussions drew against
XP-style columns  and doubles as the course card's lesson count with zero
joins. Drift guards: `lesson_repository` is the single mutation choke point and
sole sync caller; `manage.py recount_lessons` reconciles; per-mutation tests
assert the count. (Admin edits bypass the choke point  the admin says so and
the command repairs it.)

### 2. Visibility Q builders export a `prefix` parameter

`course_visibility.visible_detail_q(prefix="course__")` lets lessons apply the
*same* course-visibility rule across the join in its own querysets. One rule,
one implementation, composable from either side  the alternative (a parallel
boolean in lessons) is one rule with two implementations, and two
implementations drift.

Courses' detail Q also has one branch recipes' does not: **archived courses
stay readable to actively-enrolled students** (their progress must not vanish
because the instructor tidied up). Draft remains the hard kill switch.

### 3. Cross-app reads go through frozen refs

`CourseRef` and `EnrollmentRef` (dataclasses from courses' selectors) carry
exactly what lessons needs  identity, instructor for owner checks, status for
gating  without exposing models. `EnrollmentRef.grants_access`
(active/completed) is the single definition of "enrolled" used by every gate:
lesson content, completion writes, and the progress endpoint alike. A dropped
student keeps their history in the database but is not served it until they
re-enroll.

### 4. Course completion is write-through + self-healing read, no signals

`progress_service.complete_lesson` counts the user's completed published
lessons (its own tables); at 100% it calls
`enrollment_service.record_course_completion()`  a lessons→courses call in the
allowed direction, recording an idempotent fact (`completed_at` stamped once,
never cleared, never downgraded). The concurrent-last-two-lessons race, where
neither write sees 100%, is closed by the progress **read**: computing 100%
against a still-active enrollment records completion there too. `signals/`
stays empty by policy.

### URL prefix is configuration, not coupling

`GET /courses/{slug}/lessons/` and `GET /courses/{slug}/progress/` are lesson
data and belong to the lessons app (`api/urls/course_nested.py`), mounted under
the courses prefix by `config/urls.py`. Django tries each include in order and
falls through on no-match; the two-segment patterns cannot collide with
courses' single-segment `<str:slug>/`.

## The 403 carve-out from "hidden ⇒ 404"

Phase 2's rule protects *existence secrecy*. Lesson content introduces a case
where existence is public by design  the syllabus lists every published
lesson  and only *access* is gated. Two layers:

| Layer | Condition | Response |
|---|---|---|
| Existence | course hidden, or lesson unpublished for a non-owner | **404** (unchanged from Phase 2) |
| Gating | lesson on the public syllabus, viewer not enrolled | **403 `enrollment_required`** (401 if anonymous) |

A 404 at the gating layer would be a lie the client can disprove, and the
Next.js frontend needs the distinct code to render the "Enroll" CTA (401 → login
redirect). The 403 is reachable only after the 404 layer passes, so it never
confirms anything hidden.

## Consequences

- Either app's tests can run without the other's endpoints; `courses` remains a
  leaf.
- Import-linter contracts should pin the direction (`courses` never imports
  `lessons`; `lessons` imports only courses' `selectors`/`services`/`constants`).
- Lessons are entities with progress FKs, so the Phase 2 collection-replace
  write pattern is **prohibited** here  lesson CRUD is individual, and
  reordering is a dedicated full-array endpoint validated as exactly the
  course's lesson-id set.
- The counter is eventually consistent under concurrent recounts by one row for
  one read; it self-corrects on the next lesson write. Not worth cross-app
  locking.
