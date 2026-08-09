# ADR 0014 — Certificates & Achievements

**Status:** Accepted (Phase 8)
**Context:** Phase 8 adds `apps/certificates`: course certificates with
public verification, achievement records, and the badge foundation. This is
**not gamification** — no XP, levels, streaks, rewards or leaderboards; those
remain future phases with their own ADR.

---

## 1. Why certificates own issuance state

`apps/certificates` owns three tables — certificates, achievements, badge
definitions — and depends one way on `progress` and `courses` (public
selectors only). No content app imports certificates; nothing is pushed
into this app. Issuance is **user-triggered** (`POST
/courses/{slug}/certificate/`), pull-based: the service reads the facts it
needs and records its own. That keeps the certificate lifecycle — number
allocation, revocation, verification, future PDF rendering — confined to
one app, and it means completing a course has zero certificate side
effects until the student asks (a certificate is a claim you make, not an
event that happens to you).

The gate order mirrors the lesson content gate: **404** (course hidden) →
**403 `enrollment_required`** (visible but not a student) → **409
`course_not_completed`** (well-formed request conflicting with current
progress state — the submit-twice family, not a validation error).

## 2. Why Progress is the source of truth

Certificates never count a lesson. Completion is read from
`progress_selector.get_course_completed_at` — the
`CourseProgress.completed_at` fact stamped once by
`recalculate_course_progress`, the sole writer (ADR 0012). Re-deriving
completion here would be a second implementation of the required-lesson
rule that could disagree with the first; the entire codebase's visibility
discipline exists to prevent exactly that class of bug. Trusting the stamp
also means certificates inherit progress' semantics for free: courses are
never "un-completed", so an issued certificate can never retroactively
lose its justification. Volume achievements (`ten_courses`) read the same
app's `completed_course_count` — computed live from stamped facts, no
counter column anywhere.

## 3. Why certificate numbers are immutable

`certificate_number` and `issued_at` are written at creation and never
touched again — there is no update path in the repository to misuse. A
certificate is a *record of a fact* referenced from outside the system
(printed, framed, listed on a CV); renumbering one would invalidate paper
we cannot recall. The printable fields (`student_name`, `course_title`,
`completed_at`) are **snapshots at issuance** for the same reason — the
snapshot-completeness rule from quiz attempts (ADR 0010): what the
certificate says must not change when a course is renamed or a handle
changes, and the future PDF phase must read nothing mutable. The snapshot
is also what lets `course` be `SET_NULL` — deleting a course (an existing
API that must keep working) cannot delete or blank anyone's earned
certificate.

The one permitted mutation is `revoked_at`, stamped once by conditional
UPDATE. Revoked rows remain forever; the **partial unique** `(user,
course) WHERE revoked_at IS NULL` frees the slot so a legitimate re-issue
gets a *new* number while the audit trail keeps the old one.

Numbers are `KB-<year>-<six digits>`, allocated by reading the year's
current maximum (not a row count — revocations would make counts collide)
and retrying inside a savepoint when two issuances race; the global unique
constraint is the arbiter.

## 4. Why verification uses a UUID

Certificate numbers are sequential by design — human-facing, printable,
sortable — which makes them **enumerable**: `KB-2026-000042` implies
000041 exists. If the number were the lookup key, anyone could walk the
registry and harvest who-completed-what. So the public endpoint is keyed
only by `verification_token`, an unguessable UUID4 printed alongside the
number (as a QR code, eventually): possession of a certificate is what
grants the ability to verify it. The response is deliberately narrow —
number, course title, student's public handle *as printed*, issue date,
`valid`/`revoked` — never an email, never an internal id. Revoked
certificates verify as `revoked` rather than 404: "this was withdrawn" is
a verification answer an employer needs; a 404 would be indistinguishable
from a forgery, which is a different claim.

## 5. Why achievements are append-only

An achievement is a fact about the past — the LearningActivity precedent
(ADR 0012): facts are immutable where state is not. There is no update or
delete path; `unique (user, achievement_type)` makes awarding idempotent
(`get_or_create`), and the original `awarded_at`/`metadata` are never
rewritten by a repeat trigger. `recalculate()` is append-only repair: it
awards anything current facts justify and removes nothing — an achievement
whose conditions later lapse was still earned.

Award wiring respects the dependency arrows. Course achievements
(`course_completed`, `first_course`, `ten_courses`) are awarded during
issuance, from progress facts. `quiz_master` and `recipe_author` are
**declared but unwired**: quizzes and recipes cannot call into
certificates (content apps must not import it), so those awards will be
*derived* — certificates reading quizzes'/recipes' public selectors inside
`recalculate()` — never pushed. No model signals anywhere, per the
standing no-signals rule (ADR 0009 §4).

## 6. Why PDF generation is postponed

A PDF is a rendering of data this phase now guarantees: the printable
snapshot plus the verification URL. Rendering brings real dependencies
(a PDF library or headless browser, Thai font embedding and licensing,
layout assets, storage for generated files, a Celery job) and zero new
domain rules. Deferring it costs nothing — the future PDF phase consumes
`student_name` / `course_title` / `completed_at` / `certificate_number` /
`verification_token` exactly as stored, offline, with no live joins —
while shipping it now would couple this domain's correctness work to a
rendering stack the frontend may end up owning anyway (client-side
printing of a verification page is a legitimate v1).

## 7. Why badges are system-defined

`BadgeDefinition` is presentation, seeded by migration and curated only in
Django admin — **no CRUD API**. Badges are part of the platform's meaning:
if users or instructors could mint them, "Ten courses" would be worth
whatever the least scrupulous author says it is. Separating definition
(system-owned, bilingual Thai-first, deactivatable) from the earned fact
(the achievement row) means presentation can be re-worded or hidden
without un-earning anything, and a badge referenced by any achievement is
undeletable (`PROTECT`). The badge FK on achievements is nullable so an
award never fails just because presentation is missing — the fact
outranks the decoration.

## Consequences

- Revocation has no HTTP endpoint yet — it is a service/admin-action
  concern (`certificate_service.revoke`), owner-scoped so a future
  endpoint inherits the 404-not-yours rule.
- A certificate survives course deletion with `course_id = NULL`; its
  snapshot keeps it printable and verifiable. Uniqueness for (user, NULL)
  no longer binds — acceptable, since the course can never be completed
  again.
- `student_name` is the handle at issuance; a user who changes handles
  keeps certificates naming the old one. That is what the paper says —
  by design, not by accident.
- The sequence resets per year by construction of the number format;
  `KB-2027-000001` follows `KB-2026-000123`.
