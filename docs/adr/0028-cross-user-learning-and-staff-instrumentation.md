# ADR 0028 - Cross-user learning views and staff instrumentation

- **Status:** accepted
- **Date:** 2026-08-11
- **Phase:** back-office completion, part two

## Context

ADR 0027 gave the back office its content surfaces; four operational
views remained honest gaps: nobody could see learning progress across
users, the certificate registry, the notification log, or why the
recommendation engine ranked what it ranked. Each gap touches a rule an
earlier ADR set deliberately, so closing them needed decisions, not just
endpoints.

## Decisions

### 1. Progress stays single-user everywhere except the staff lens

`/admin/progress/` adds three reads: a platform summary, per-course
enrollment funnels, and a per-course learner roster (progress percent,
computed live as always - no counter is stored anywhere new). The roster
merges three sources at the view edge with two batch queries per page:
enrollments (via a new courses public selector), completed counts and
`last_viewed_at` maxima (new cross-user selectors in progress, isolated
in `admin_progress_selector` so every owner-scoped read stays visibly
single-user). "Drop-off" is reported as what the data can actually say:
a learner's last activity time, and null for never-started.

### 2. Certificate revocation is attributable or it does not happen

`POST /admin/certificates/{id}/revoke/` requires a reason and records
`revoked_by` + `revoked_reason` (new columns) with the stamp - revoking
rewrites the evidentiary answer of someone's public verification link,
so an anonymous revocation is not a feature. A second revocation is a
409 (`certificate_already_revoked`), never a silent success: the first
operator's reason must stay the recorded one. The owner-scoped
`revoke()` service survives untouched; staff go through
`revoke_as_staff`. `/admin/certificates/` is the registry, searchable by
number, printed name, course and holder.

### 3. Broadcast is a producer like any other - and the only human one

`announcement` joins `NotificationEventType` (the enum change ADR 0016
requires). `POST /admin/notifications/broadcast/` bulk-creates rows for
every **active** account that has not opted out of announcements - the
same per-event preference machinery as machine-produced types, no
special channel. `GET /admin/notifications/` is the cross-user log.
What was **not** built, stated on the page itself: delivery/bounce
status (notifications are in-app only; `read_at` is the only honest
receipt) and a template model (bodies are free text; five event types
remain hardcoded Thai strings in the service).

### 4. Scores exist for staff eyes; the public feed keeps none

The scoring pipeline's internal seam (`_score_and_rank`) now returns
`ScoredCandidate`s; the public feed functions strip the score at their
boundary exactly as before, and `preview_scored` keeps it for
`GET /admin/recommendations/preview/?username=…` - the "run the engine
as user X" debug lens, resolved with the *target user* as the card
viewer so staff see precisely that user's feed, not a staff-widened one.
This amends ADR 0018 §10 for the staff surface only: scores and reason
codes cross the admin boundary; the user's raw history still never does.
`/admin/recommendations/config/` exposes the deployed weight constants,
read-only - weights are code with tests, not configuration. Click-through
stats were **not** built: the platform keeps no impression/click log.

## Consequences

- The dashboard's "ยังไม่มี API" cards for users, enrollments, reviews
  and certificates now show real counts; only assistant usage remains a
  disclosed gap.
- `PaginatedFilterSerializer` (apps.common) is now the base of every
  admin filter across eight apps.
- Two schema-visible privacy widenings, both staff-gated: learner
  rosters (progress) and recommendation scores. Tests pin the 401/403
  gates on every new route and that the public feed still carries no
  score field.
- The revocation columns make certificates two fields less immutable;
  both are stamp-once and never rendered on any public payload.
