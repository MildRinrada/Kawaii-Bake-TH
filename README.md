# KawaiiBake 🧁

An advanced bakery learning platform — recipes, video tutorials, courses,
lessons, quizzes, Q&A, reviews, gallery, AI assistants and gamification.

> **Status:** Phases 1–14 complete — auth/users, recipes/categories,
> courses/lessons, quizzes/questions, reviews/favorites, learner progress,
> the Thai-first AI assistant, certificates/achievements, the gamification
> foundation, the notification center, the community layer (gallery +
> Q&A), deterministic recommendations with ingredient substitution, the
> rewards economy, and the completed profile/personalization layer. The
> remaining feature apps are still stubs. Phase 15 adds the Next.js
> frontend foundation (structure-first — visual design pending) in
> `frontend/`.

## Architecture

Separated frontend and backend. **Django is API-only**: it serves JSON at
`/api/v1/` and renders no pages. Next.js owns the entire user interface.

| Layer | Technology |
|---|---|
| Backend | Python 3.12+, Django 5, Django REST Framework |
| Database | PostgreSQL (SQLite for local development) |
| Cache / broker | Redis |
| Workers | Celery |
| Frontend | Next.js, TypeScript, React, Tailwind CSS |
| AI | Pluggable provider package (`ai/`) |
| Deploy | Docker |

## Quick Start

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements/development.txt   # Unix: .venv/bin/pip

cp .env.example .env          # optional — sane defaults work out of the box
.venv/Scripts/python manage.py migrate
.venv/Scripts/python manage.py createsuperuser
.venv/Scripts/python manage.py runserver
```

Development defaults to SQLite, console email, and eager Celery tasks, so no
PostgreSQL or Redis is needed to run locally. Set `DB_ENGINE=postgres` to use
PostgreSQL.

- API root: `http://localhost:8000/api/v1/`
- Interactive docs: `http://localhost:8000/api/docs/`
- Admin: `http://localhost:8000/admin/`

### Tests

```bash
.venv/Scripts/python -m pytest
```

### Frontend types

```bash
.venv/Scripts/python manage.py spectacular --file schema.yml
```

Generate TypeScript types from `schema.yml` in the Next.js project.

## What Phase 1 Delivers

**Authentication** — registration, login, logout, password reset, email
verification, password change, account activation/deactivation, rate limiting,
CSRF protection. Session cookies today, behind a seam that makes swapping to JWT
a one-module change.

**Users** — custom user model (email login, separate public handle), profile
(avatar, bio, birthday, location, experience level, favourite categories) and
preferences (privacy, learning, notifications). Exactly three tables.

## What Phase 2 Delivers

**Recipes** — full CRUD with nested ingredients and steps, a draft/published/
archived lifecycle with publish-time completeness checks, public/unlisted/private
visibility, cover and gallery images, author-supplied nutrition, and Unicode
slugs that work with Thai titles.

**Listings** — pagination, filtering (category, difficulty, ingredient, author,
total time), seven orderings, and search behind a swappable backend.

**Categories** — a curated taxonomy seeded to match the slugs already stored in
user profiles, with live published-recipe counts.

## What Phase 3 Delivers

**Courses** — instructor-owned courses with the draft/published/archived
lifecycle, publish-time completeness checks, idempotent enrollment with soft
drops that preserve history, and archived courses that stay readable to
enrolled students.

**Lessons** — public syllabus with enrollment-gated content, free preview
lessons, drag-and-drop reordering, per-lesson recipe links that degrade
gracefully, completion tracking with automatic course completion, and an
un-complete that keeps history.

## What Phase 4 Delivers

**Question bank** — reusable, tagged, per-type validated questions (single
choice, multiple choice, true/false) owned by their authors, with permanent
content freezing once a question has been answered anywhere — historical
integrity over editability, with versioning fields prepared for the future.

**Quizzes** — draft/published/archived quizzes composing bank questions by
reference, publish-time completeness checks (including the bank's own verdict
on every answer set), attempts that snapshot the composition at start and
grade only against that snapshot, exact-set scoring with pass/fail, retry via
unlimited attempt history, and answer keys that structurally cannot appear in
any taker-facing payload. Lessons may reference a quiz; quiz logic never
crosses into lessons.

## What Phase 5 Delivers

**Reviews** — 1–5 star ratings with optional comments on recipes and courses,
one active review per user per target, owner editing, staff moderation
(hide/restore), soft deletion that preserves history, and read-only rating
statistics (average, count, star distribution) computed live — no stored
rating columns.

**Favorites** — idempotent bookmark toggles on recipes and courses, and a
`/users/me/favorites/` list with full target cards that shows only what the
caller could currently open: private content silently leaves the list and
returns with the content; archived courses stay for their enrolled students.

## What Phase 6 Delivers

**Progress** — its own domain (`apps/progress`, extracted from lessons):
timestamp-based lesson completion with permanent first-completion history,
course completion derived live from lesson rows (stamped once, never
downgraded), a per-course progress report, a `/me/progress/` dashboard
overview with a flat query count, and an append-only `LearningActivity`
ledger — the streak/XP/leaderboard foundation, with no gamification
implemented yet.

## What Phase 7 Delivers

**AI Assistant** — Thai-first conversations (`th` default, `en` supported)
with the assistant, optionally anchored to a recipe, lesson or course whose
content is loaded live through each app's own visibility rules — private
content is denied at creation, enrollment-gated lessons return the same 403
as reading them, and content that later disappears degrades gracefully.
Versioned prompt templates (old conversations keep the prompt they started
under), append-only transcripts, per-call usage logging, per-user rate
limiting, and pluggable providers behind the framework-free `ai/` package —
the deterministic offline mock by default, so no API key is needed to
develop or test. No agents, RAG or gamification yet.

## What Phase 8 Delivers

**Certificates** — user-requested course certificates issued only against
the progress app's stamped completion fact (never recomputed), with
globally unique `KB-YYYY-NNNNNN` numbers, an immutable printable snapshot
(student handle, course title, completion date — ready for the future PDF
phase), stamp-once revocation that preserves history and frees the slot
for a re-issue, and anonymous employer verification keyed only by an
unguessable UUID token — never the enumerable number, never an email.

**Achievements** — append-only earned facts (course completed, first
course, ten courses; quiz/recipe types declared for later) awarded
idempotently at issuance and repairable via a pull-based `recalculate`,
presented through system-owned bilingual badges seeded th+en. No XP,
levels, streaks or leaderboards — gamification remains a future phase.

## What Phase 9 Delivers

**Gamification** — an append-only XP ledger derived entirely from facts
other domains own (10/100/20/25/5 XP for lessons, courses, quizzes,
certificates, reviews — values in one service), a progressive level curve
recomputed from the ledger, daily streaks derived from the learning
activity calendar (never incremented), an idempotent per-user
recalculation endpoint, and a public leaderboard exposing exactly the
public handle, level and total XP at a flat query count. No signals
anywhere; no domain knows gamification exists. Rewards, coupons, missions
and seasonal events remain future phases.

## What Phase 10 Delivers

**Notifications** — an in-app notification center fed by three wired
events (a review on your content, a new or returning student in your
course, a first-earned achievement), delivered post-commit and
best-effort so a notification problem can never fail the action that
caused it. Rows are immutable, content-FK-free snapshots that survive
deletion of what they mention and carry only public handles; the feed
paginates with a live unread count, read stamps are once-and-idempotent
(single and bulk), and per-event preferences default to enabled with
zero seeded rows. No email, push, realtime or digests yet — the delivery
seam is ready for them.

## What Phase 11 Delivers

**Gallery** — "I baked this" showcase posts with ordered image galleries:
validated multipart uploads that never leave files behind on rejection,
exact-set reordering through PATCH, publish/unpublish visibility that
fails closed, references restricted to publicly listed recipes/courses,
and hard deletion that verifiably removes every stored file.

**Q&A** — community question threads on recipes and courses (a separate
domain from the quiz question bank): public reading, authenticated
answers, author editing, staff hide/restore, soft-deleted threads that
preserve answer history while vanishing from every API surface, and an
at-most-one accepted answer that replaces atomically and self-clears when
the accepted answer is deleted. Answers and acceptances notify through
the Phase 10 sink — never yourself, always opt-outable. No voting,
reputation, likes or AI answers yet.

## What Phase 12 Delivers

**Recommendations** — deterministic recipe and course feeds computed per
request from facts other domains own (favorites, reviews, enrollments,
profile taste, ratings): a bounded public candidate pool scored by named
weighted features, ranked with id tie-breaks, category-diversified, and
explained through aggregate reason codes — no scores, no raw behavior, no
emails in any payload. Anonymous and brand-new users get the same
deterministic cold-start feed; hidden, unlisted, draft and archived
content never appears for anyone. No stored recommendation state, no ML —
both are declared seams.

**Ingredient substitution** — `/recipes/{slug}/substitutions/` answers
"what can I swap in this recipe" from a curated in-code rule registry
matched on the Thai-safe normalised ingredient names recipes already
store: Thai/English aliases fold to one rule, ratios appear only where
the conversion is established, confidence is deliberately coarse,
allergens are cautions not guarantees, and unknown ingredients return an
honest empty list.

## What Phase 13 Delivers

**Rewards economy** — a per-user reward account with a materialized,
never-negative balance and an immutable, append-only ledger where every
entry snapshots what happened, why, how much, and the balance afterward.
Earning is pull-based from facts the other domains own (completed
lessons and courses, submitted quizzes, certificates, achievements),
keyed to identified source events and made idempotent by a database
unique constraint — retries, replays and races cannot grant twice.
Spending exists as a guarded service primitive (conditional-UPDATE
debits; no shop yet), staff corrections are audited ledger entries with
required reasons, reward reasons carry authored Thai and English titles,
and a conservative `reconcile_rewards` command (dry-run by default)
repairs by appending and recomputing only — never deleting, never
clawing back.

## What Phase 14 Delivers

**Profile & personalization** — the Phase 1 profile layer completed as
the platform's explicit-personalization source: favourite categories are
now real taxonomy relations (the migration ADR 0006 planned — validated
against live categories, self-healing on deletion, same API shape), the
language preference is Thai-first and pinned assistant-compatible
(`th`/`en`), the recommendation fact carries exactly what the user
explicitly said (never behavior), profile completion is derived — never
stored — and a read-only `/me/settings/` composition returns profile,
preferences, notification settings and completion in one request while
every write stays with its owning domain. Privacy remains enforced
through the single public projection, with leak tests across every
public payload.

See [docs/API.md](docs/API.md) for the endpoint surface, the permission matrix
and the Next.js integration contract.

## Project Layout

```
config/         # Settings, root URLs, WSGI/ASGI, Celery
apps/           # Feature apps — one per domain
media/          # User uploads (not committed)
ai/             # Framework-free AI package
infrastructure/ # Adapters for cache, email, storage, queue, search, logging
frontend/       # Next.js app (Phase 15 — structure-first; see frontend/README.md)
docs/           # Documentation + ADRs
tests/          # Cross-app integration & e2e tests
scripts/        # Operational scripts
docker/         # Dockerfiles & compose files
requirements/   # Layered dependency files
```

## Documentation

- [Architecture](docs/Architecture.md) — layering, the credential seam, DRF rules
- [API](docs/API.md) — endpoints, auth flow, error contract, Next.js integration
- [Database](docs/Database.md) — the three tables and what was deliberately omitted
- [Folder Structure](docs/FolderStructure.md)
- [Coding Guidelines](docs/CodingGuidelines.md)
- [Decision Records](docs/adr/README.md)

## License

TBD
