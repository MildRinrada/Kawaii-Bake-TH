# KawaiiBake  API

Django is **API-only**. It serves JSON at `/api/v1/` and renders no pages; the
Next.js frontend owns all UI. The only non-API route is Django admin.

- **OpenAPI schema:** `GET /api/schema/`  or `python manage.py spectacular --file schema.yml`
- **Interactive docs:** `GET /api/docs/`
- The frontend generates its TypeScript types from that schema.

## Authentication

Phase 1 uses **session cookies** (httpOnly), not JWT. Rationale and the
migration path are in [ADR 0007](adr/0007-session-auth-for-phase-1.md).

### Why cookies rather than a bearer token

| | Session cookie | Bearer token in `localStorage` |
|---|---|---|
| Logout | Real, server-side, immediate | Token stays valid until expiry |
| XSS exposure | JavaScript cannot read it | Total account takeover |
| Extra tables | None | Blacklist app adds two |

### Client flow (Next.js)

Every request must send `credentials: "include"`. Unsafe methods must echo the
CSRF token.

```ts
// 1. Once, before the first unsafe request:
await fetch(`${API}/api/v1/auth/csrf/`, { credentials: "include" });

// 2. Read the cookie the server just set:
const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1] ?? "";

// 3. Send it back on every POST/PATCH/DELETE:
await fetch(`${API}/api/v1/auth/login/`, {
  method: "POST",
  credentials: "include",
  headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
  body: JSON.stringify({ email, password, remember_me: true }),
});
```

`GET /api/v1/auth/me/` is the session bootstrap: it returns **200** with
`{"user": null}` when nobody is signed in, so page loads never treat "anonymous"
as an error.

The payload carries `is_staff`  the **caller's own** staff flag, so a client
can decide whether to render an admin surface at all (ADR 0022). It is
presentation input only: staff-widened reads (`scope=all`) and every
moderation write are still authorised server-side from `request.user`, and a
non-staff caller who forces an admin route simply sees the public catalogue.

### Swapping in JWT later

`settings.AUTH_CREDENTIAL_ISSUER` names the class that establishes credentials.
Writing `api/credentials/jwt_issuer.py` and repointing that setting is the whole
change  no view, serializer, service, repository, selector or URL is touched.
`/api/v1/auth/token/refresh/` is already reserved in the URL conf.

## Endpoints

### Authentication  `/api/v1/auth/`

| Method | Path | Auth | Success | Notes |
|---|---|---|---|---|
| GET | `/csrf/` |  | 204 | Sets the `csrftoken` cookie |
| POST | `/register/` |  | 201 | Returns the identity payload; does **not** sign in |
| GET | `/username-available/` |  | 200 | `?username=` → `{username, available}`; advisory, rate limited per IP |
| POST | `/login/` |  | 200 | `{status, user}`; sets `sessionid` |
| POST | `/logout/` | session | 204 | POST-only; deletes the server-side session |
| GET | `/me/` | optional | 200 | `{"user": …}` or `{"user": null}` |
| POST | `/password-reset/` |  | **202 always** | Never reveals whether the account exists |
| POST | `/password-reset/confirm/` |  | 200 | Invalidates all other sessions |
| POST | `/password-change/` | session | 200 | Keeps the caller signed in, drops other sessions |
| POST | `/verify-email/` |  | 200 | Confirms the address; does **not** sign in |
| POST | `/verify-email/resend/` | session | 202 | Rate limited |

### Recipes  `/api/v1/recipes/`

| Method | Path | Auth | Success | Notes |
|---|---|---|---|---|
| GET | `/` | optional | 200 | Paginated; filter, order, search, `scope` |
| POST | `/` | session | 201 | Creates a **draft**; nested ingredients and steps |
<!-- Read payloads carry `id` alongside `slug` (ADR 0023): slug is the
     addressing identity, `id` exists so a caller can fill another app's
     `recipe_id` write field  the gallery post attachment. -->

| GET | `/search/` | optional | 200 | `q` required; relevance ordering |
| GET | `/{slug}/` | optional | 200 / 404 | |
| PATCH | `/{slug}/` | owner/admin | 200 | Partial; `status` not accepted |
| DELETE | `/{slug}/` | owner/admin | 204 | Permanent; archive is the reversible option |
| POST | `/{slug}/publish/` | owner/admin | 200 / 400 | Runs the completeness checks |
| POST | `/{slug}/unpublish/` | owner/admin | 200 | Back to draft; keeps `published_at` |
| POST | `/{slug}/archive/` | owner/admin | 200 | Reversible |
| POST | `/{slug}/images/` | owner/admin | 201 | `multipart/form-data` |
| DELETE | `/{slug}/images/{id}/` | owner/admin | 204 | |

### Recipe categories  `/api/v1/recipe-categories/`

| Method | Path | Auth | Success | Notes |
|---|---|---|---|---|
| GET | `/` | optional | 200 | Unpaginated; includes published `recipe_count` |

### Courses  `/api/v1/courses/`

| Method | Path | Auth | Success | Notes |
|---|---|---|---|---|
| GET | `/` | optional | 200 | Paginated; `search` (title/summary/description), filter category/difficulty/instructor; `scope`; per-viewer `is_enrolled`/`is_completed`; carries `total_duration_minutes`, `rating_average`/`rating_count` (stored aggregates, ADR 0021) |
| POST | `/` | session | 201 | Creates a draft |
| GET | `/{slug}/` | optional | 200 / 404 | |
| PATCH | `/{slug}/` | owner/admin | 200 | `status` not accepted; slug frozen after publish |
| DELETE | `/{slug}/` | owner/admin | 204 | Permanent; archive is the reversible option |
| POST | `/{slug}/publish\|unpublish\|archive/` | owner/admin | 200 / 400 | Publish validates title, description, thumbnail, ≥1 published lesson |
| POST | `/{slug}/enroll/` | session | 201 first / 200 after | Idempotent; 404 on hidden course; 400 `own_course` |
| DELETE | `/{slug}/unenroll/` | session | 204 | Soft drop; history kept |
| GET | `/{slug}/lessons/` | optional | 200 | **Syllabus**  lesson metadata only (learner state lives at the progress endpoints) |
| POST | `/{slug}/lessons/` | owner/admin | 201 | Appends at the end |
| POST | `/{slug}/lessons/reorder/` | owner/admin | 200 / 400 | Full ordered id array; diff reported on mismatch |
| GET | `/{slug}/progress/` | enrolled | 200 / 403 | Aggregate + per-lesson  served by the **progress** app |

### Lessons  `/api/v1/lessons/`

| Method | Path | Auth | Success | Notes |
|---|---|---|---|---|
| GET | `/{id}/` | see gate below | 200 / 401 / 403 / 404 | Full content incl. video, linked recipe and linked quiz |
| PATCH / DELETE | `/{id}/` | owner/admin | 200 / 204 | Delete renumbers survivors |

### Progress  nested under lessons, courses and `/api/v1/me/`

Owned by ``apps/progress`` (ADR 0012); routes are mounted under the prefixes
of what they decorate.

| Method | Path | Auth | Success | Notes |
|---|---|---|---|---|
| POST | `/lessons/{id}/complete/` | enrolled | 200 | Idempotent; returns `course_completed`; records the day's activity fact |
| DELETE | `/lessons/{id}/complete/` | enrolled | 200 | Clears `completed_at`; `first_completed_at` history survives |
| GET | `/courses/{slug}/progress/` | enrolled | 200 / 403 | Aggregate + per-lesson; the self-healing completion read |
| GET | `/me/progress/` | session | 200 | `{courses: [...]}`  per-course completion overview, flat query count |

### Questions  `/api/v1/questions/` (authenticated authoring surface)

| Method | Path | Auth | Success | Notes |
|---|---|---|---|---|
| GET | `/` | session | 200 | Paginated **own bank**; filter `type`/`difficulty`/`tag`/`search`; staff `scope=all` |
| POST | `/` | session | 201 | Nested choices, atomic; 400 `invalid_choices` lists every rule broken |
| GET | `/tags/` | session | 200 | All tags, alphabetical |
| GET | `/{id}/` | owner/admin | 200 / 404 | The **only** payload carrying `is_correct` |
| PATCH | `/{id}/` | owner/admin | 200 / 409 | Content locked once frozen; `explanation`/`difficulty`/`tags` always editable |
| DELETE | `/{id}/` | owner/admin | 204 / 409 | 409 `question_frozen` (has attempts) or `question_in_use` (in a quiz) |

### Quizzes  `/api/v1/quizzes/`

| Method | Path | Auth | Success | Notes |
|---|---|---|---|---|
| GET | `/` | optional | 200 | Paginated; `owner`, `ordering`, `scope` |
| POST | `/` | session | 201 | Creates a draft; optional ordered `question_ids` |
| GET | `/{slug}/` | optional | 200 / 404 | One shape for every viewer; questions **without correctness** |
| PATCH | `/{slug}/` | owner/admin | 200 | `question_ids` replaces the whole composition  reorder **is** this call |
| DELETE | `/{slug}/` | owner/admin | 204 / 409 | 409 `quiz_has_attempts` once history exists  archive instead |
| POST | `/{slug}/publish\|unpublish\|archive/` | owner/admin | 200 / 400 | Publish validates title, description, ≥1 question, **every question's answers** |
| POST | `/{slug}/start/` | session | 201 / 200 | Idempotent per user; freezes questions + snapshots the composition |
| POST | `/{slug}/submit/` | session | 200 | Grades against the **snapshot**; omitted questions = skipped (wrong) |
| GET | `/{slug}/attempts/` | session | 200 | Own history, newest first |
| GET | `/{slug}/attempts/{id}/` | own/admin | 200 / 404 | Per-question review; explanations only after submit |
| DELETE | `/{slug}/attempts/{id}/` | own | 204 / 409 | Abandon an open attempt; submitted history is permanent |

### Reviews  nested under recipes and courses

| Method | Path | Auth | Success | Notes |
|---|---|---|---|---|
| GET | `/recipes/{slug}/reviews/` · `/courses/{slug}/reviews/` | optional | 200 | Paginated **active** reviews, newest first, reviewer embedded |
| POST | same | session | 201 | One active review per user per target; 400 `own_content`; 409 `already_reviewed` |
| GET | `/recipes/{slug}/rating/` · `/courses/{slug}/rating/` | optional | 200 | `{average, count, distribution}`  computed, never stored |
| PATCH | `/reviews/{id}/` | owner/admin | 200 | Owner edits `rating`/`comment`; `status` (active/hidden) is staff-only → 403 |
| DELETE | `/reviews/{id}/` | owner/admin | 204 | **Soft** delete  history survives; the author may review again |

### Favorites  nested under recipes, courses and users

| Method | Path | Auth | Success | Notes |
|---|---|---|---|---|
| POST | `/recipes/{slug}/favorite/` · `/courses/{slug}/favorite/` | session | 201 / 200 | Idempotent toggle; hidden target ⇒ 404 |
| DELETE | same | session | 204 | Idempotent |
| GET | `/users/me/favorites/` | session | 200 | Paginated, `?type=recipe\|course`; target cards embedded; only currently-visible targets appear |

### AI Assistant  `/api/v1/assistant/` and `/api/v1/me/`

| Method | Path | Auth | Success | Notes |
|---|---|---|---|---|
| POST | `/assistant/conversations/` | session | 201 | `{language, context_type, recipe_id?\|lesson_id?\|course_id?}`; hidden target ⇒ 404; gated lesson ⇒ 403 `enrollment_required`; mismatched ids ⇒ 400 `invalid_context` |
| GET | `/assistant/conversations/{id}/` | session (owner) | 200 / 404 | `{conversation, messages}`  messages paginated, oldest first |
| POST | `/assistant/conversations/{id}/messages/` | session (owner) | 201 / 404 / 429 / 503 | Sends the user's message, returns the assistant's reply; provider failure ⇒ 503 `assistant_unavailable` with the user message kept |
| GET | `/me/assistant/conversations/` | session | 200 | Paginated, most recently active first; only the caller's |

Messages are append-only  there is no edit or delete. Replies come from
the provider configured by `AI_PROVIDER` (the offline deterministic mock by
default; no API key needed for local work). Each conversation stamps the
prompt template version it was created under and keeps it for life; sends
are rate-limited per user before the provider is called. See ADR 0013.

### Certificates  nested under courses, `/api/v1/me/` and `/api/v1/certificates/`

| Method | Path | Auth | Success | Notes |
|---|---|---|---|---|
| POST | `/courses/{slug}/certificate/` | session | 201 / 200 | Issue (201) or return existing (200); hidden ⇒ 404, not a student ⇒ 403 `enrollment_required`, incomplete ⇒ 409 `course_not_completed` |
| GET | `/me/certificates/` | session | 200 | Paginated, newest first, revoked included with `status` |
| GET | `/certificates/{verification_token}/` | **anonymous** | 200 / 404 | Employer verification by UUID token; returns `valid`/`revoked`; never an email |
| GET | `/me/achievements/` | session | 200 | Paginated earned achievements with bilingual badge metadata |
| GET | `/achievements/` | **anonymous** | 200 | The active badge catalogue  *what there is to earn*, unpaginated. Pair with `/me/achievements/` (*what I have earned*) to render locked badges (ADR 0024). Inactive badges are hidden here without un-earning anything |

Completion is read from the progress app's stamped fact  certificates
never count lessons. Certificates are immutable once issued (number,
dates and the printable snapshot never change); revocation is stamp-once,
keeps the row, and frees the (user, course) slot for a re-issue with a new
number. The sequential `KB-YYYY-NNNNNN` number is never a lookup key 
only the unguessable token verifies. See ADR 0014.

### Gamification  `/api/v1/me/` and `/api/v1/leaderboard/`

| Method | Path | Auth | Success | Notes |
|---|---|---|---|---|
| GET | `/me/gamification/` | session | 200 | `{level, streak, recent_transactions}`  derived on first read. `level.xp_for_next_level` states the current level's XP span so clients draw the bar without restating the curve (ADR 0024) |
| POST | `/me/gamification/recalculate/` | session | 200 | Rebuild XP + streak from the domains' facts; idempotent |
| GET | `/me/streak/` | session | 200 | `{current, longest, last_activity}` |
| GET | `/leaderboard/` | **anonymous** | 200 | Paginated; each row is exactly `{public_handle, level, total_xp}`  never an email |

All XP is derived: the ledger reconciles against fact counts owned by
progress, certificates, quizzes and reviews (10/100/20/25/5 XP 
lesson/course/quiz/certificate/review), so recalculating twice changes
nothing and nothing is ever clawed back. Levels and streaks are computed
rows rebuilt from the ledger and from progress' activity calendar. See
ADR 0015.

### Notifications  `/api/v1/me/notifications/`

| Method | Path | Auth | Success | Notes |
|---|---|---|---|---|
| GET | `/me/notifications/` | session | 200 | Paginated, newest first; `?unread=true`; body carries live `unread_count`; strictly the caller's own |
| POST | `/me/notifications/{id}/read/` | session (owner) | 200 / 404 | Stamp-once `read_at`; repeat calls stay 200 with the same stamp |
| POST | `/me/notifications/read-all/` | session | 200 | One conditional bulk UPDATE; returns `{marked_read}`  rows newly stamped |
| GET | `/me/notifications/preferences/` | session | 200 | Every supported event type; absent row resolves to `true` |
| PATCH | `/me/notifications/preferences/` | session | 200 / 400 | Strict `{event_type: bool}` subset; unknown event types rejected |

There is no create endpoint: notifications exist only because a producer
service (reviews, courses, certificates) called the notification service
after its own transaction committed. Three wired events 
`review_received`, `course_enrollment`, `achievement_earned`. Rows are
immutable snapshots (title/body/actor handle/link) with no FK to content;
delivery is best-effort and never fails the producer. See ADR 0016.

### Gallery  `/api/v1/gallery/`

| Method | Path | Auth | Success | Notes |
|---|---|---|---|---|
| GET | `/gallery/` | optional | 200 | Paginated feed, newest first; anon sees published, owners also their own; filters `recipe_id`, `course_id`, `category`, `author` |
| POST | `/gallery/` | session | 201 | `{caption?, status?, recipe_id?, course_id?}`; references must be publicly listed ⇒ else 400 `invalid_reference` |
| GET | `/gallery/{id}/` | optional | 200 / 404 | Same rule as the list; unpublished-and-not-yours ⇒ 404 |
| PATCH | `/gallery/{id}/` | owner/admin | 200 / 404 | caption/status/references; `image_ids` (exact set) reorders  400 `invalid_order` otherwise |
| DELETE | `/gallery/{id}/` | owner/admin | 204 / 404 | **Hard** delete; every stored image file is removed |
| POST | `/gallery/{id}/images/` | owner/admin | 201 | One multipart image; byte-validated before storage; max 10/post |
| DELETE | `/gallery/{id}/images/{image_id}/` | owner/admin | 204 / 404 | Row and file together |

### Q&A  `/api/v1/qa/`

Community discussion  a different domain from `/questions/` (the quiz
item bank); see ADR 0017 §14.

| Method | Path | Auth | Success | Notes |
|---|---|---|---|---|
| GET | `/qa/threads/` | optional | 200 | Paginated; filters `recipe_id`, `course_id`, `search` (title/body) |
| POST | `/qa/threads/` | session | 201 | `{target_type, target_slug, title, body?}`; hidden target ⇒ 404 |
| GET | `/qa/threads/{id}/` | optional | 200 / 404 | Active public; hidden ⇒ author/staff only; deleted ⇒ 404 for everyone |
| PATCH | `/qa/threads/{id}/` | author/staff | 200 | title/body; `status` (hide/restore) is staff-only ⇒ 403 otherwise |
| DELETE | `/qa/threads/{id}/` | author/staff | 204 | **Soft** delete  history survives, no API returns it again |
| GET | `/qa/threads/{id}/answers/` | optional | 200 / 404 | Oldest first; hidden/deleted thread ⇒ 404, never an empty page |
| POST | `/qa/threads/{id}/answers/` | session | 201 / 409 | Active threads only; notifies the asker (never yourself) |
| POST | `/qa/threads/{id}/accept/` | thread author/staff | 200 | `{answer_id}`; replaces any previous accepted answer atomically; notifies the answerer |
| PATCH / DELETE | `/qa/answers/{id}/` | answer author/staff | 200 / 204 | Hard delete; deleting the accepted answer clears the thread's pointer |

### Rewards  `/api/v1/me/rewards/` and `/api/v1/rewards/`

| Method | Path | Auth | Success | Notes |
|---|---|---|---|---|
| GET | `/me/rewards/` | session | 200 | Balance + lifetime earned/spent; zeros before first earn (no row is minted by a GET) |
| GET | `/me/rewards/transactions/` | session | 200 | Own ledger only, newest first, paginated; each entry: kind, amount, balance_after, `reason {code, title_th, title_en}`, note, actor_handle, created_at |
| POST | `/me/rewards/claim/` | session | 200 | Settles earnings up to current facts  idempotent and monotonic; replaying grants nothing. `{claimed, points, balance}` |
| POST | `/rewards/adjustments/` | staff | 201 / 404 / 409 | `{username, amount, reason, idempotency_key?}`  audited ledger entry; reason required; 409 `insufficient_balance` on overdraw (balance can never go negative) |

Earning is pull-based (the gamification `recalculate` pattern, ADR 0019):
call `claim` after learning actions or on page load. Every earning is
keyed to an identified source fact and unique at the database, so
duplicate delivery  retries, double clicks, races  cannot grant twice.
Spending exists at the service layer only; a user-facing spend endpoint
arrives with the future shop phase. No email, no event keys, no internal
ids in any payload.

### Recommendations  `/api/v1/recommendations/` and nested under recipes

| Method | Path | Auth | Success | Notes |
|---|---|---|---|---|
| GET | `/recommendations/recipes/` | optional | 200 | Paginated ranked feed; authenticated ⇒ personalized, anonymous ⇒ deterministic cold start |
| GET | `/recommendations/courses/` | optional | 200 | Same shape for courses; enrolled/completed courses never appear |
| GET | `/recipes/{slug}/substitutions/` | optional | 200 / 404 | Substitution candidates per ingredient; optional `?ingredient=` filter; recipe visibility governs, hidden ⇒ 404 |

Each feed item is `{reasons: [code…], recipe|course: card}`  the card is
the content app's own list shape, the reasons are aggregate evidence codes
(`matches_your_favorite_categories`, `highly_rated`, …). Scores, feature
values and raw behavior never appear, and neither does an email. Each
substitution entry is `{ingredient, normalized, substitutions: [{name,
ratio, note, confidence}]}`  `ratio` is empty when no reliable conversion
exists, `confidence` is coarse (`high/medium/low`) on purpose, and an
unknown ingredient returns an empty candidate list, never a guess. See
ADR 0018.

### Users  `/api/v1/users/` and `/api/v1/me/settings/`

| Method | Path | Auth | Success | Notes |
|---|---|---|---|---|
| GET | `/profile/` | session | 200 | The caller's own profile |
| PATCH | `/profile/update/` | session | 200 | Partial; accepts `multipart/form-data` for `avatar` and `cover`; `favorite_categories` slugs are validated against the **live** taxonomy (Phase 14)  unknown slug ⇒ 400, nothing persists |
| GET | `/preferences/` | session | 200 | Privacy, learning and interface settings; `locale` is `th`/`en` (Thai default), assistant-compatible |
| PATCH | `/preferences/` | session | 200 | Partial |
| GET | `/<username>/` | optional | 200 / 404 | Redacted per the owner's privacy settings |
| POST | `/account/deactivate/` | session | 204 | Disables the account and ends the session |
| GET | `/api/v1/me/settings/` | session | 200 | **Read-only composition** (Phase 14): `{profile, preferences, notifications, profile_completion}`  the notifications block comes from that app's own effective-preferences read; writes still go to each owner's endpoint. Completion is derived (`{completed, total, percent, missing}`), never stored |

Literal paths are routed before `<username>`, and those words are also in
`RESERVED_USERNAMES`, so a handle can never shadow an endpoint.

### Legal documents - `/api/v1/legal/`

| Method | Path | Auth | Success | Notes |
|---|---|---|---|---|
| GET | `/` | none | 200 | All four documents' metadata (kind, title, version, updated_at) |
| GET | `/{kind}/` | none | 200 / 404 | Full text; kinds: `terms`, `privacy`, `pdpa`, `cookie` |
| PATCH | `/{kind}/` | staff | 200 | Edit title and/or body; every change bumps `version` atomically |

Bodies use the RichText mini-format (`##` headings, `-`/`1.` lists,
`**bold**`, `*italic*`, `__underline__`) rendered client-side as elements,
never HTML. Reads are public because a visitor must be able to read what
they consent to at registration.

## Request and response shapes

### `POST /auth/register/`

```json
{ "email": "baker@example.com", "username": "baker",
  "first_name": "มินตรา", "last_name": "อบอุ่น",
  "password": "…", "password_confirm": "…", "accept_terms": true }
```

`first_name`/`last_name` are required - certificates print them - and
`accept_terms` must be an explicit `true` (PDPA consent; the timestamp is
stored on the account). Registration does **not** start a session: the
account confirms its email first (`/verify-email/{uid}/{token}` on the
frontend → `POST /auth/verify-email/`), then signs in itself.

```json
{ "id": 2, "username": "baker", "email": "baker@example.com",
  "is_email_verified": false, "experience_level": "beginner", "avatar_url": null }
```

### `GET /auth/username-available/?username=baker`

```json
{ "username": "baker", "available": false }
```

Advisory only  a malformed or reserved handle answers `available: false`
rather than 400 (the caller is a live keystroke check), and two racing
sign-ups are still settled by registration's unique constraint. Rate
limited per IP (`USERNAME_CHECK_RATE_LIMIT_*`, default 30/min) so it
cannot be scripted into a bulk enumeration scan.

### `POST /auth/login/`

```json
{ "email": "baker@example.com", "password": "…", "remember_me": true }
```

```json
{ "status": "authenticated", "user": { … } }
```

`status` is `authenticated` today and will be `mfa_required` once two-factor
auth ships  the field exists now so that addition is not a breaking change.

`remember_me: true` gives a 30-day session; omitted or `false` gives a session
cookie that dies with the browser.

### `PATCH /users/profile/update/`

All fields optional. **Absent** means "leave unchanged"; an explicit `null` on a
nullable field (`birthday`, `location`, `avatar`, `cover`) clears it.

```json
{ "display_name": "Baker", "bio": "Sourdough obsessive.",
  "birthday": "1995-05-05", "location": "Bangkok",
  "experience_level": "intermediate",
  "favorite_categories": ["bread", "macaron"] }
```

Unknown keys are **rejected with 400**, not silently ignored  a typo like
`favourite_categories` fails loudly rather than returning a misleading 200.

Identity and permission fields (`email`, `username`, `is_staff`, …) are absent
from the serializer entirely, so they cannot be mass-assigned.

**Images (`avatar`, `cover`)** go in a `multipart/form-data` request. Both are
validated by decoding the bytes, never by trusting `content_type`: allowed
formats are JPEG/PNG/WebP (SVG is excluded  it can carry script), the cap is
2 MB for an avatar and 4 MB for a cover, and the client filename is used only
for its extension. `cover` arrives **already cropped**  the browser performs
the fixed-ratio pan/zoom crop and uploads only the result, so there is no
server-side image pipeline and no original to re-crop from.

`cover_url` is returned on the **own-profile** shape only
(`GET /users/profile/`); the public profile payload does not carry it, because
nothing renders a stranger's banner yet.

## Recipes

### Permission matrix

Hidden always means **404**, never 403  a 403 would confirm the slug exists.

| status | visibility | anon | signed-in stranger | owner | admin |
|---|---|---|---|---|---|
| draft | any | – | – | list via `?scope=mine`, detail 200 | full |
| published | public | list + detail | list + detail | full | full |
| published | unlisted | **detail only** | **detail only** | full | full |
| published | private | – | – | full | full |
| archived | any | – | – | `?scope=mine`, detail 200 | full |

Write permissions: create requires a session; edit, delete and status changes
require ownership or staff.

**`unlisted` is the asymmetric case**: reachable by direct link, absent from
every listing *and from search*. Being undiscoverable is the entire point.

### `scope`

| Value | Meaning |
|---|---|
| `public` (default) | Published and public only |
| `mine` | Every recipe you own, any status. **401** when anonymous |
| `all` | Everything  staff only; silently narrowed to `public` otherwise |

`scope=mine` pins the author to the session user, so no combination of query
parameters can reach another author's drafts. Your own drafts deliberately do
**not** appear in the default browse feed.

### Lifecycle

```
DRAFT ──publish (validated)──▶ PUBLISHED ──archive──▶ ARCHIVED
  ▲ └──────── archive ──────────────┘                    │
  └──────────────── unpublish / restore ─────────────────┘
```

Every transition is reversible; only `DELETE` is terminal. Publishing is
idempotent, and an archived recipe is **re-validated** on its way back to
published.

Completeness is checked **at publish, not on every save**  a draft must be
saveable while incomplete. `POST /publish/` returns every unmet requirement at
once so the frontend can render a checklist:

```json
{"error": {"code": "recipe_not_publishable",
           "message": "This recipe is not ready to publish.",
           "details": {"ingredients": ["Add at least one ingredient."],
                       "steps": ["Add at least one step."],
                       "category_slugs": ["Choose at least one category."],
                       "cover_image": ["Add a cover image."]}}}
```

Requirements to publish: a title, ≥1 ingredient, ≥1 step, ≥1 category, a cover image.

### Listing parameters

| Parameter | Example | Notes |
|---|---|---|
| `search` | `?search=ครัวซองต์` | Title and summary |
| `category` | `?category=cake,bread` | **Comma-separated**, not repeated params |
| `difficulty` | `?difficulty=easy,medium` | |
| `ingredient` | `?ingredient=butter` | Indexed match on the normalised name |
| `author` | `?author=chef` | |
| `max_total_minutes` | `?max_total_minutes=60` | |
| `ordering` | `?ordering=quickest` | `newest` (default), `oldest`, `title`, `quickest`, `difficulty`, `popular`, `relevance` |
| `scope` | `?scope=mine` | See above |
| `page`, `page_size` | `?page=2&page_size=50` | `page_size` capped at 100 |

Unknown parameters are **rejected with 400**, not ignored  `?catgeory=cake`
silently returning everything is a miserable bug to chase.

One deliberate asymmetry: an unknown category *in a filter* returns an empty
page (categories are dynamic; a bookmarked URL must not break when staff rename
one), whereas an unknown category *in a write body* is a 400 `invalid_category`.
Filtering is a query; assignment is an assertion.

`ordering=popular` is a working placeholder mapped to publication date until
`favorites` exists. The API contract will not change when the implementation does.

### Writes

`POST /recipes/` and `PATCH /recipes/{slug}/` take JSON with nested arrays:

```json
{"title": "ครัวซองต์ไส้ช็อกโกแลต",
 "prep_minutes": 40, "cook_minutes": 25, "servings": 6, "difficulty": "hard",
 "category_slugs": ["pastry", "chocolate"],
 "ingredients": [{"name": "แป้งสาลี", "quantity": "500.000", "unit": "g"}],
 "steps": [{"body": "นวดแป้งแล้วพักในตู้เย็น"}],
 "nutrition": {"calories_kcal": "420.00"}}
```

- **PATCH semantics:** an absent key is unchanged. A supplied `ingredients` or
  `steps` array **replaces that collection entirely**  which is also how
  reordering is expressed, since `position` is derived from array order and is
  never accepted from the client.
- `"nutrition": null` clears it; omitting it leaves it alone.
- `status` is **not accepted** on create or update. Publishing goes through
  `/publish/` so the completeness checks cannot be bypassed. `visibility` *is*
  editable, because it has no precondition.
- `cover_image` is uploaded as `multipart/form-data`; gallery images use
  `POST /{slug}/images/`. Nested arrays are JSON-only.
- Slugs are generated from the title and **frozen once first published** 
  changing one would break every shared link. There is no redirect table yet, so
  a published typo is permanent (see Known limitations).

### Thai text

Slugs use `allow_unicode=True`, so Thai titles produce Thai slugs; plain
slugification would return an empty string and every Thai recipe would get a
random slug. Slugification is lossy for Thai (combining tone marks are dropped,
as accents are for Latin text), which is fine for a URL identifier and is why
collisions get a random suffix. Routes use `<str:slug>`, not `<slug:slug>`,
whose regex would reject Thai entirely.

## Courses & Lessons

### Permission matrix

Course visibility mirrors recipes (hidden ⇒ 404), with one extra branch:
**archived courses stay readable to actively-enrolled students**.

| course status / visibility | anon | stranger | enrolled student | instructor | admin |
|---|---|---|---|---|---|
| draft, any | – | – | – | full | full |
| published + public | list + detail | list + detail | + content | full | full |
| published + unlisted | detail only | detail only | + content | full | full |
| published + private | – | – | – ¹ | full | full |
| archived, any | – | – | **detail + content** | full | full |

¹ Making a course private hides it even from enrolled students; archived is the
"closed but honoured" state.

### The lesson content gate (404 vs 403)

Lessons introduce the one principled carve-out from "hidden ⇒ 404":

| Layer | Condition | Response |
|---|---|---|
| Existence | course hidden from viewer, or lesson unpublished | **404** `not_found` |
| Gating | lesson is on the public syllabus; viewer just isn't enrolled | **403** `enrollment_required`  or **401** if anonymous |

The syllabus already makes the lesson's existence public, so a 404 at the
gating layer would be a lie. The distinct codes are load-bearing for the
frontend: 401 → redirect to login; 403 `enrollment_required` → render the
Enroll CTA. Preview lessons (`is_preview`) skip the gate for reading;
**completing** any lesson still requires enrollment.

The syllabus endpoint returns metadata only (title, duration, preview flag,
`has_video`)  never `content` or `video_url`.

### Course lifecycle

Same machine as recipes (all transitions reversible, publish idempotent and
re-validated from archived). Publish requires: title, a real description, a
thumbnail, and **≥ 1 published lesson**  reported all at once as a checklist
in `details`. The lesson requirement reads a counter the lessons app maintains;
see [ADR 0009](adr/0009-courses-lessons-boundary.md).

### Enrollment flow

```
POST enroll      → no row: create ACTIVE (201)
                 → dropped: reactivate  COMPLETED if ever finished, else ACTIVE (200)
                 → active/completed: no-op (200)
DELETE unenroll  → status = DROPPED (204). Nothing is deleted.
```

- One enrollment row per (user, course), forever; concurrent enrolls resolve
  via the unique constraint.
- Instructors cannot enroll in their own course (400 `own_course`); only
  published courses are enrollable.
- Dropping hides the course, its content **and its progress report** until
  re-enrollment, which restores everything  including COMPLETED status.

### Lesson progress flow (owned by the progress app since Phase 6)

```
POST /lessons/{id}/complete/   → {lesson_id, completed, completed_at,
                                  first_completed_at, course_completed}
                               → completion is a nullable timestamp;
                                 first_completed_at stamped once, ever
                               → if every published lesson is now complete:
                                 CourseProgress.completed_at stamped once AND
                                 enrollment → COMPLETED (the Phase 3 contract)
                               → the day's LearningActivity fact recorded
DELETE /lessons/{id}/complete/ → completed=false; first_completed_at survives;
                                 a completed course is never downgraded
GET /courses/{slug}/progress/  → {total_lessons, completed_lessons, percent,
                                  completed_at, enrollment_status, lessons: [...]}
GET /me/progress/              → {courses: [{id, slug, title, completed_lessons,
                                  total_lessons, percentage, completed_at}]}
```

Completing requires an access-granting enrollment even on preview lessons 
reading is free, progress is not. Course completion is **derived** from
lesson completion at write and read time (write-through + self-healing read),
never counter-maintained, and never downgrades  not by un-completing a
lesson, not by the instructor adding new lessons.

### Lesson ordering

Built for drag-and-drop: `POST /courses/{slug}/lessons/reorder/` takes
`{"lesson_ids": [...]}`  the full id array, exactly the course's lesson set.
Missing, duplicate or foreign ids return 400 with the diff
(`missing_ids` / `duplicate_ids` / `unknown_ids`). New lessons append at the
end; deleting renumbers the survivors densely.

### Course ↔ recipe links

A lesson may reference the recipe it teaches (`recipe_id`). Linking validates
the author can see the recipe; on read, the embed is resolved with the
**viewer's** identity, so a recipe that has since gone private serializes as
`recipe: null`  degrades, never leaks.

## Questions & Quizzes

### Permission matrix

The question bank is a private authoring surface: anonymous users see nothing,
and someone else's question id is the same 404 as a nonexistent one. Quizzes
follow the standard status × visibility axes, with one extra branch: an
**archived quiz stays readable to anyone who has attempted it** (results
history must not vanish), while new attempts always require `published`.

| quiz status / visibility | anon | authenticated | has attempted | owner | admin |
|---|---|---|---|---|---|
| draft, any | – | – | – | full | full |
| published + public | list + detail | + start/submit | + history | full | full |
| published + unlisted | detail only | + start/submit | + history | full | full |
| published + private | – | – | – | full | full |
| archived, any | – | – | **detail + history** | full | full |

`unlisted` is the intended pairing for lesson-linked quizzes: absent from
browse, reachable only through the (enrollment-gated) lesson.

### The answer key never travels

Every taker-facing payload  quiz detail, start, submit, attempt review  is
built from DTOs that structurally have no `is_correct` field, and choices are
always ordered by `position`. The only endpoint that renders correctness is
the owner's own `GET /questions/{id}/`. After submitting, takers receive
`was_correct` and the question's `explanation`  the outcome, never the key.

### Attempt flow

```
POST start   → open attempt exists: return it (200)
             → else, in ONE transaction (201):
                 freeze every composed question (frozen_at, stamped once)
                 create the attempt (max_score fixed now)
                 create empty answer rows (position + points_possible snapshot)
POST submit  → validated against the snapshot (diff in details on mismatch)
             → graded from the snapshot + frozen answer keys only
             → one-shot: a second submit finds no open attempt (404)
DELETE attempts/{id} → abandons an open attempt; submitted rows are permanent
```

Because grading never reads the live composition, instructors may edit a
quiz's `question_ids` at any time  in-flight attempts finish against what
they were shown. Frozen questions refuse content edits with 409
`question_frozen`; duplicate the question to change it (versioning via
`supersedes` is the prepared future path  [ADR 0010](adr/0010-question-bank-and-quiz-boundary.md)).

### Scoring

Single choice and true/false grade exact-one; multiple choice grades
**exact-set** (all correct choices, nothing else  no partial credit).
Skipped questions are incorrect. `percentage` is `score/max_score` to two
decimals; `passed` is `percentage >= pass_percent`. All figures are stamped
onto the attempt at grading time and never recomputed.

### Lesson ↔ quiz links

A lesson may reference one quiz (`quiz_id`)  a reference only; quiz logic
never crosses into lessons. The embed carries `{id, slug, title,
pass_percent, question_count}` (never questions) and is resolved with the
viewer's identity, so a hidden quiz serializes as `quiz: null`.

## Reviews & Favorites

### Review lifecycle

`active → hidden` (moderation, staff) and `active → deleted` (the author, via
DELETE)  nothing is ever hard-deleted. Listings and rating statistics count
**active** reviews only, so hiding a review changes the average instantly.
Deleting frees the one-active-review-per-target slot: the author may write a
fresh review, and the old row survives as history. Reviewing requires seeing
the target (hidden ⇒ 404) and not owning it (400 `own_content`).

### Rating statistics

`GET …/rating/` computes `{average (2 dp, null when unreviewed), count,
distribution per star}` in one aggregate query  there are no stored rating
columns anywhere ([ADR 0011](adr/0011-review-target-architecture.md)); the
selector is the future caching seam.

### Favorites semantics

A favorite is an idempotent toggle (the enroll pattern: 201 first, 200 after,
204 on remove, always). The list shows only targets the caller could
currently open  a recipe that went private silently leaves the list (the
bookmark row survives and returns with the recipe); an archived course stays
for its enrolled student. Both behaviours are the content apps' own
visibility rules composed across the join, not favorites-specific logic.

## AI Assistant

### Conversation flow

```
POST /assistant/conversations/  {language:"th", context_type:"recipe", recipe_id:12}
        → 201 {id, prompt_version:"1", …}          (target visibility checked here)
POST /assistant/conversations/12/messages/  {content:"ทำไมเค้กยุบตรงกลาง?"}
        → 201 {role:"assistant", content:"…", provider, model_name, token_*}
GET  /assistant/conversations/12/
        → 200 {conversation:{…}, messages:{count, next, previous, results:[…]}}
GET  /me/assistant/conversations/               (paginated, mine only)
```

### Context rules

Creating a typed conversation requires exactly the matching id
(`context_type:"recipe"` ⇒ `recipe_id`, nothing else) and the target must be
readable **by the caller**: hidden ⇒ 404, enrollment-gated lesson content ⇒
403 `enrollment_required`  the same two-layer rule as reading the lesson
itself. After creation the check is lenient: a target that is later deleted
or made private silently degrades the conversation to context-free answers;
history is never lost and hidden content is never injected.

### What the model sees

The system prompt is a server-owned versioned template plus a fenced,
data-labelled context block (recipe ingredients/steps, lesson content,
course syllabus) loaded live through the content apps' public visibility
APIs. User messages travel only as `user` turns  they are never
concatenated into the system prompt, and the `system` role is never stored,
so stored content cannot rewrite the assistant's instructions.

### Failure semantics

| Situation | Response |
|---|---|
| Send allowance exhausted (per user) | 429 `rate_limited`  before the provider is called |
| Provider down / misconfigured | 503 `assistant_unavailable`  the user's message **is saved**; no reply row appears; retrying is safe |
| Message empty or > 4000 chars | 400 |

## Certificates & Achievements

### Issuance flow

```
POST /courses/khanom-course/certificate/
  404  course hidden from you            (existence layer, as everywhere)
  403  enrollment_required               (visible, but you are not a student)
  409  course_not_completed              (progress has not stamped completion)
  201  {certificate_number:"KB-2026-000001", verification_token:"…", …}
  200  same body on every later call     (idempotent  one active per course)
```

The response carries the **printable snapshot**  `student_name`,
`course_title`, `completed_at`, `certificate_number`  frozen at issuance.
Renaming the course or changing your handle later never rewrites an issued
certificate; the future PDF phase reads exactly these fields.

### Verification (public)

`GET /certificates/{verification_token}/` needs no account  it is the
employer-facing check for a printed certificate. The token is an
unguessable UUID; the sequential certificate number is deliberately not
routable, so the registry cannot be enumerated. Revoked certificates
return `status: "revoked"` (a verification answer), not 404 (which would
look like a forgery). The payload never includes an email or internal id.

### Achievements

Earned facts, append-only: unique per (user, type), never edited, never
removed. `course_completed` and `first_course` are awarded at first
issuance; `ten_courses` when the progress fact count reaches ten.
`quiz_master` / `recipe_author` are declared (badges seeded) but not yet
awarded  recorded in ADR 0014. Badge presentation is bilingual
(`title_th` first-class) and system-owned; there is no badge CRUD API.

## Gamification

### Everything is derived

```
POST /me/gamification/recalculate/
        reads:  progress (lessons, courses, activity days)
                certificates (distinct certified courses)
                quizzes (distinct submitted quizzes)
                reviews (active reviews)
        appends: only the ledger entries the facts justify but the
                 ledger lacks  →  running twice appends nothing
        returns: {level:{current_level, current_xp, total_xp},
                  streak:{current, longest, last_activity},
                  recent_transactions:[…]}
```

The XP ledger is append-only  no entry is ever edited or deleted, and a
fact that later disappears (a deleted review) never claws back earned XP.
`UserLevel` and `DailyStreak` are recomputed rows: droppable, rebuildable,
never incremented in place. The level curve is progressive (level *L* →
*L+1* costs *L* × 100 XP); a streak stays alive if its newest activity day
is today or yesterday.

### Freshness

XP is current as of the last recalculation  user-triggered in this phase,
scheduled later. The summary read derives missing rows on first access but
does not re-reconcile per request.

## Notifications

### Delivery semantics

```
producer service (review / enrollment / award)
        │  business transaction commits
        ▼
notification_service.notify(…)        registered via transaction.on_commit
        ▼
preference gate → snapshot INSERT     best-effort: failures are logged
                                      and swallowed  the producer never
                                      sees them
```

A notification is a private, immutable snapshot of an event: what it says
was true when it happened, and it survives deletion of the content it
mentions (no content FKs). The `link` is a frontend path that may go
stale  a stale link 404s at its own endpoint, never here. Actor identity
is the public handle only; emails structurally cannot appear.

### Wired events

| Event | Trigger | Recipient |
|---|---|---|
| `review_received` | a review is created on your recipe/course | content owner |
| `course_enrollment` | a student newly enrolls or returns (idempotent no-ops are silent) | instructor |
| `achievement_earned` | first award of an achievement | the earner |
| `qa_answer_received` *(Phase 11)* | someone answers your question | thread author |
| `qa_answer_accepted` *(Phase 11)* | your answer is marked accepted (first time per answer) | answer author |

Adding an event type is an ADR/docs change, not just another call.
Preferences are per event type, in-app axis only  the email-channel
toggles remain on `users` preferences; absent row means enabled.

## Error contract

Every error uses one envelope, produced by a single DRF exception handler
(`apps/common/api/exception_handler.py`):

```json
{ "error": {
    "code": "invalid_credentials",
    "message": "Email or password is incorrect.",
    "details": { "email": ["This field is required."] },
    "request_id": "b3f1…"
} }
```

- `code`  stable machine string; branch on this, not on `message`.
- `details`  `{field: [messages]}`, present for validation failures.
- `request_id`  also returned as the `X-Request-ID` header; quote it in bug reports.

| Code | HTTP | Meaning |
|---|---|---|
| `validation_error` | 400 | Malformed payload or unknown field |
| `invalid_token` | 400 | Reset/verification link invalid or expired |
| `not_authenticated` | 401 | No valid session |
| `invalid_credentials` | 401 | Wrong email **or** password (deliberately indistinguishable) |
| `permission_denied` | 403 | Authenticated but not allowed |
| `account_disabled` | 403 | Account deactivated |
| `email_not_verified` | 403 | Verification required and missing |
| `not_found` | 404 | Missing **or** not visible to you |
| `email_already_registered` | 409 | Email taken |
| `username_taken` | 409 | Handle taken |
| `email_already_verified` | 409 | Address already confirmed |
| `invalid_category` | 400 | Category slug unknown or inactive |
| `recipe_not_publishable` | 400 | Incomplete; `details` lists every requirement |
| `course_not_publishable` | 400 | Incomplete course; `details` is the checklist |
| `enrollment_required` | 403 | Lesson content/progress needs enrollment |
| `own_course` | 400 | Instructors cannot enroll in their own course |
| `not_enrollable` | 400 | Course is not published |
| `not_enrolled` | 404 | Unenrolling without ever enrolling |
| `invalid_recipe` | 400 | Linked recipe absent or not visible to the author |
| `invalid_reorder` | 400 | Reorder array ≠ the course's lesson set; diff in `details` |
| `invalid_choices` | 400 | Answer choices break the question type's rules; all problems in `details` |
| `invalid_questions` | 400 | Quiz composition has unknown/foreign/duplicate question ids |
| `invalid_quiz` | 400 | Linked quiz absent or not visible to the lesson author |
| `quiz_not_publishable` | 400 | Incomplete quiz; `details` is the checklist incl. per-question answer problems |
| `quiz_not_available` | 400 | Starting a quiz that is not published (or has no questions) |
| `invalid_submission` | 400 | Answers don't match the attempt snapshot; diff in `details` |
| `no_open_attempt` | 404 | Submitting with nothing in progress |
| `question_frozen` | 409 | Content edit/delete of a question with attempt history |
| `question_in_use` | 409 | Deleting a question a quiz still references |
| `quiz_has_attempts` | 409 | Deleting a quiz with attempt history  archive instead |
| `attempt_already_submitted` | 409 | Second submit, or abandoning a submitted attempt |
| `own_content` | 400 | Authors cannot review their own recipe/course |
| `already_reviewed` | 409 | An active review already exists  edit it instead |
| `slug_immutable` | 409 | Slug of a published recipe/course cannot change |
| `slug_taken` | 409 | Requested slug already used |
| `limit_exceeded` | 400 | Collection over its size cap |
| `rate_limited` | 429 | Too many attempts |
| `internal_error` | 500 | Unexpected; details are logged, never returned |

## Pagination

List endpoints return DRF's standard envelope:

```json
{"count": 137, "next": "…?page=3", "previous": "…?page=1", "results": [...]}
```

Default 20 per page, `page_size` capped at 100. A page past the end returns
**404** `not_found`. Ordering always carries an `-id` tiebreaker, so rows sharing
a sort key cannot reshuffle between pages and produce duplicates or gaps.

The envelope shape is deliberate: switching to cursor pagination later, when the
per-request `COUNT(*)` becomes the bottleneck, preserves it exactly.

## Known limitations

- **Published slugs are frozen.** Fixing a typo in a published recipe's URL is
  not possible; doing it properly needs a slug-history table serving 301s.
- **`ordering=popular` is a placeholder** mapped to publication date.
- **PostgreSQL search is not exercised by the test suite**  the default
  portable backend is. See [ADR 0008](adr/0008-cross-app-model-references.md).

## Security behaviour worth knowing

- **No account enumeration.** `/password-reset/` always returns 202. Wrong
  password and unknown email return an identical 401 body. A private profile
  returns 404, never 403.
- **Rate limiting** is cache-backed (no tables). Login is keyed by *IP + email* 
  IP alone both punishes shared networks and is bypassed by rotating addresses.
- **Verification links never sign you in.** A forwarded email must not become a
  session.
- **Password change invalidates every other session** via the session-auth hash;
  the caller stays signed in.
- **Deactivation invalidates live sessions** on their next request, because the
  auth backend re-checks `is_active` on every session restore.

## Security & threat watching  `/api/v1/security/` and `/api/v1/admin/security/`

Public  two endpoints, both anonymous-safe:

| Method | Path | Auth | Success | Notes |
|---|---|---|---|---|
| GET | `/security/client-policy/` | **anonymous** | 200 | `{guard_mode, exempt_authenticated, report_signals}`  the env-configured browser-guard posture. A settings read; no database access, no user data |
| POST | `/security/client-signals/` | **anonymous** | 201 | Report one browser-observed signal. Accepts **only** `devtools_opened`, `view_source_attempt`, `context_menu_attempt`, `console_tamper`; anything else ⇒ 400. Throttled (`SECURITY_SIGNAL_RATE`, default `30/min`). Answers `{"recorded": bool}` and nothing more |

Staff (`is_staff`)  the dashboard. Every view declares `IsAdminUser` itself;
the `admin/` prefix is naming, not permission:

| Method | Path | Auth | Success | Notes |
|---|---|---|---|---|
| GET | `/admin/security/summary/` | staff | 200 | Totals, per-band profile counts (all four bands always present), 24h/7d event counts, per-kind counts, top 5 offenders |
| GET | `/admin/security/vocabulary/` | staff | 200 | Every signal kind, level and review state with its label, so the dashboard's filters are never hard-coded client-side |
| GET | `/admin/security/events/` | staff | 200 | Paginated, newest first. Filters `kind`, `severity`, `ip`, `search` (path/UA), `since_hours`. An unknown filter value is a 400, not a silent ignore |
| GET | `/admin/security/profiles/` | staff | 200 | Paginated offenders. Filters `level`, `review_state`, `blocked`, `search`; `ordering` ∈ `-score\|score\|-last_seen_at\|last_seen_at` |
| GET | `/admin/security/profiles/{id}/` | staff | 200 / 404 | Profile plus its 20 most recent events |
| POST | `/admin/security/profiles/{id}/block/` | staff | 200 | `{minutes}` (1 … 43200). Blocks always expire |
| DELETE | `/admin/security/profiles/{id}/block/` | staff | 200 | Lift immediately |
| POST | `/admin/security/profiles/{id}/review/` | staff | 200 | `{state: acknowledged\|ignored, note?}`. `open` is rejected  a profile returns to the queue only through fresh activity |

A source's `level` is banded from a decaying score (half-life 12h):
`low < 15 ≤ medium < 45 ≤ high < 85 ≤ critical`. `score` is the stored
value, `current_score` the same value decayed to now. Events are
append-only and carry the severity of their **own** weight, so re-tuning
weights never rewrites history; the profile is a cache that
`manage.py recount_threats --dry-run` re-derives from the event log.

Detection is server-side and cannot be forged by a client: trap paths
(`/.env`, `/wp-login.php`, …), backup-file suffixes, traversal, SQLi/XSS
markers, attack-tool user agents, scripted clients, 404 sweeps, auth-failure
bursts and request floods. Search-engine crawlers are matched *before* the
automation list and scored zero. See ADR 0025  including the part that says
plainly that a web page cannot prevent DevTools from opening.

### Security configuration

| Setting | Default | Purpose |
|---|---|---|
| `SECURITY_WATCH_ENABLED` | `true` | Master switch for the server-side detectors |
| `SECURITY_BLOCKING_ENABLED` | `true` | Whether an active block is enforced (observe-only when off) |
| `SECURITY_AUTO_BLOCK` | `false` | Block automatically on reaching `critical` |
| `SECURITY_AUTO_BLOCK_MINUTES` | `60` | Length of an automatic block |
| `SECURITY_TRUSTED_IPS` | `127.0.0.1,::1` | Never scored, never blocked  put the operator's address here **before** testing a honeypot |
| `SECURITY_CLIENT_GUARD_MODE` | `detect` | `off` / `detect` (observe only) / `deter` (also intercept F12, Ctrl+Shift+I/J, Ctrl+U, right-click). An unrecognised value falls back to `off` |
| `SECURITY_GUARD_EXEMPT_AUTHENTICATED` | `true` | Leave signed-in visitors alone |
| `SECURITY_CLIENT_REPORTS_ENABLED` | `true` | Whether the public ingest stores anything |
| `SECURITY_SIGNAL_RATE` | `30/min` | Throttle on the public ingest |
| `SECURITY_INGEST_SECRET` | *(empty)* | Shared secret letting the Next.js edge forward a visitor's real address for trap hits Django never sees. Empty disables forwarding |

## Back-office admin API - `/api/v1/admin/…` (ADR 0027)

The management surfaces behind the `/admin` frontend. Same convention as
security: the `admin/` prefix is naming only - every view declares
`IsAdminUser` itself. Every list validates its query strictly (an
unknown filter is a 400, not a silent ignore) and paginates with the
standard envelope unless noted.

**Categories - `/admin/recipe-categories/`**

| Method | Path | Success | Notes |
|---|---|---|---|
| GET | `/admin/recipe-categories/` | 200 | Unpaginated array, **inactive included**, `recipe_count` annotated. The public list additionally gained `image_url` |
| POST | `/admin/recipe-categories/` | 201 | Multipart. `name` required; `slug` derives from the name (Thai-safe) when omitted; optional `description`, `icon`, `display_order`, `is_active`, `image`. Duplicate slug ⇒ 409 `duplicate_category_slug` |
| PATCH | `/admin/recipe-categories/{id}/` | 200 | Partial; multipart or JSON. JSON `{"image": null}` removes the tile photo (and its stored file) |
| DELETE | `/admin/recipe-categories/{id}/` | 204 | Unlinks recipe/course assignments; deletes no content |

**Users - `/admin/users/`**

| Method | Path | Success | Notes |
|---|---|---|---|
| GET | `/admin/users/` | 200 | Roster with profile joined. Filters `search` (username/email/legal name/display name), `status` (`active`/`suspended`), `verified`, `staff`; `ordering` ∈ `newest\|oldest\|username\|recently_active`. Rows carry PII (email, legal name) - staff-only by construction |
| GET | `/admin/users/{id}/` | 200 / 404 | One account |
| PATCH | `/admin/users/{id}/` | 200 | Partial: `first_name`, `last_name`, `is_active` (maintains `deactivated_at` like self-service), `is_staff`, `is_email_verified` (emergency override; stamps/clears `email_verified_at` like the real flow). Editing your **own** access flags, or any flag of a superuser ⇒ 403 `protected_account` |

**Achievements - `/admin/achievements/`**

| Method | Path | Success | Notes |
|---|---|---|---|
| GET | `/admin/achievements/` | 200 | Unpaginated badge catalogue, inactive included, `awarded_count` annotated |
| POST | `/admin/achievements/` | 201 | `slug`, `title_th`, `title_en` required. Duplicate ⇒ 409 `duplicate_badge_slug`. Creating a badge never awards it |
| PATCH | `/admin/achievements/{slug}/` | 200 | Partial edit |
| DELETE | `/admin/achievements/{slug}/` | 204 | Only while unawarded; else 409 `badge_in_use` (deactivate instead - PROTECT keeps earned presentation alive) |
| GET | `/admin/achievements/awards/` | 200 | The cross-user ledger, read-only by design (append-only facts, ADR 0012). Filters `search` (earner), `achievement_type` |

**Reviews - `/admin/reviews/`**

| Method | Path | Success | Notes |
|---|---|---|---|
| GET | `/admin/reviews/` | 200 | Flat list across recipes **and** courses with target titles. Filters `rating`, `status` (`active`/`hidden`/`deleted`), `target` (`recipe`/`course`), `search` (comment/reviewer). Without `status`, tombstones are excluded. Mutations stay on `PATCH/DELETE /reviews/{id}/` - there is deliberately no endpoint that edits review text |

**Favorites - `/admin/favorites/`**

| Method | Path | Success | Notes |
|---|---|---|---|
| GET | `/admin/favorites/` | 200 | Every favorite across users, owner + target embedded. Filters `type` (`recipe`/`course`), `search` (owner username / target title) |
| GET | `/admin/favorites/top/` | 200 | `{recipes: [...], courses: [...]}` - top ten by live count. No admin write path exists: a favorite is a user's private signal |

Related changes on public routes, all narrow-only (they intersect the
visibility rule and can never widen it): `GET /gallery/` accepts `status`
(`published`/`unpublished`), and `GET /recipes/` / `GET /courses/` accept
`status` (`draft`/`published`/`archived`) - a public viewer asking for
drafts simply gets an empty page; staff use it as the
Draft/Published/Archived filter.

Roster/registry conveniences: `GET /admin/users/` also accepts
`joined_days` (trailing-window "new users" count) and its rows carry
`experience_level`; `GET /admin/reviews/` and `GET /admin/certificates/`
accept an exact-match `username` so a per-user activity count cannot be
inflated by fuzzy search hits.

**Progress - `/admin/progress/` (ADR 0028)**

| Method | Path | Success | Notes |
|---|---|---|---|
| GET | `/admin/progress/summary/` | 200 | Platform totals: enrollments by status, distinct learners, lesson completions, active learners over 7 days |
| GET | `/admin/progress/courses/` | 200 | Per-course enrollment funnel (`enrolled/active/completed/dropped`, `completion_rate`), most enrolled first. Filter `search` (title) |
| GET | `/admin/progress/courses/{slug}/enrollments/` | 200 / 404 | The learner roster: per-learner completed lessons, percent (computed live), enrollment state and last activity (`Max(last_viewed_at)` - null means never started, the drop-off signal). Filters `status`, `search` |

**Certificates - `/admin/certificates/`**

| Method | Path | Success | Notes |
|---|---|---|---|
| GET | `/admin/certificates/` | 200 | The platform registry. `search` matches number / printed name / course / holder; `status` ∈ `valid\|revoked` |
| POST | `/admin/certificates/{id}/revoke/` | 200 | Body `{reason}` (required). Records `revoked_by` + `revoked_reason` with the stamp. Already revoked ⇒ 409 `certificate_already_revoked` - the first operator's reason stays. The public verification answer flips to `revoked`, never to missing |

**Certificate templates - `/admin/certificates/templates/` (ADR 0029)**

| Method | Path | Success | Notes |
|---|---|---|---|
| GET | `/admin/certificates/templates/` | 200 | Unpaginated rows for courses that have a design (status `draft`/`published`, last editor). Courses without a row use the built-in default |
| GET | `/admin/certificates/templates/{slug}/` | 200 / 404 | The draft/published design pair; a first read seeds the draft from the default design |
| PUT | `/admin/certificates/templates/{slug}/` | 200 | The designer's autosave: replaces the draft. The document is validated (closed element kinds, numeric bounds, <=60 elements, **<=3 signatures**, length-capped strings) - a design is data, never markup |
| POST | `/admin/certificates/templates/{slug}/publish/` | 200 | Draft becomes the production design; stamps who/when. Saving and publishing are deliberately different acts |
| POST | `/admin/certificates/templates/{slug}/reset/` | 200 | Draft := published version (or the default when never published) |
| DELETE | `/admin/certificates/templates/{slug}/` | 204 | Drop the row - the course returns to the built-in default design |

**Notifications - `/admin/notifications/`**

| Method | Path | Success | Notes |
|---|---|---|---|
| GET | `/admin/notifications/` | 200 | Cross-user log with read state. Filters `search`, `event_type`, `unread` |
| POST | `/admin/notifications/broadcast/` | 201 | `{title, body?, link?}` → `{recipients}`. Creates an `announcement` for every active account that has not opted out - the new sixth event type, same preference machinery as the rest. In-app only: there is no email channel, so no delivered/bounced status exists to report |
| GET | `/admin/notifications/stats/` | 200 | Hub numbers: campaigns by status, snapshots created today, delivered/read totals (ADR 0030) |
| GET/POST | `/admin/notifications/campaigns/` | 200 / 201 / 400 | Staff campaigns. Filters `status`, `search`. Create as `draft` or `scheduled` (future `scheduled_at` else 400 `invalid_schedule`); `audience` is a closed JSON document validated server-side (400 `invalid_audience`) |
| GET/PATCH/DELETE | `/admin/notifications/campaigns/{id}/` | 200 / 204 / 409 | Edit only `draft`/`scheduled`; delete only `draft`/`canceled`. Sent campaigns are immutable evidence - 409 `campaign_state` |
| POST | `/admin/notifications/campaigns/{id}/send/` | 200 / 400 / 409 | Deliver now: resolves the audience, drops announcement opt-outs, renders `{{user_name}}`/`{{course_name}}` per recipient, bulk-creates snapshots with a `campaign` backreference. Unresolvable variables → 400 `unresolvable_variables` |
| POST | `/admin/notifications/campaigns/{id}/cancel/` | 200 / 409 | Call off a scheduled send |
| GET | `/admin/notifications/campaigns/{id}/analytics/` | 200 / 404 | `recipients`, `delivered`, `read`, `unread`, `read_rate`, `sent_at` - real receipts only, no click tracking exists |
| POST | `/admin/notifications/audience/estimate/` | 200 / 400 | `{audience}` → `{count}` via the same resolve-then-drop-opt-outs pipeline a send uses |
| GET/POST | `/admin/notifications/templates/` | 200 / 201 | Reusable composer templates (admin-side config, never user preferences) |
| PATCH/DELETE | `/admin/notifications/templates/{id}/` | 200 / 204 / 404 | Edit fields or toggle `is_archived`; delete is allowed - templates are config, not history |

**Recommendations - `/admin/recommendations/`**

| Method | Path | Success | Notes |
|---|---|---|---|
| GET | `/admin/recommendations/preview/` | 200 / 404 | `?username=&kind=recipes\|courses` - the live pipeline as that user, **scores attached** (top 50). Cards resolve with the target user as viewer, so staff see exactly that user's feed. ADR 0018 §10 amended for this staff seam only; the public feed still never carries a score, and raw history never crosses either boundary |
| GET | `/admin/recommendations/config/` | 200 | The deployed scoring weights, read-only - weights are code, not configuration |

## Email links point at the frontend

Reset and verification emails link to `FRONTEND_BASE_URL`, not Django:

```
http://localhost:3000/reset-password/<uidb64>/<token>
http://localhost:3000/verify-email/<uidb64>/<token>
```

The Next.js page reads the two path params and POSTs them back as
`{uid, token, new_password}` or `{uid, token}`.

## Backend ↔ frontend configuration

| Setting | Purpose |
|---|---|
| `FRONTEND_BASE_URL` | Origin used to build email links |
| `FRONTEND_PASSWORD_RESET_PATH` | Frontend route for reset (default `/reset-password`) |
| `FRONTEND_EMAIL_VERIFY_PATH` | Frontend route for verification (default `/verify-email`) |
| `CORS_ALLOWED_ORIGINS` | Frontend origins allowed to call the API |
| `CORS_ALLOW_CREDENTIALS` | Must stay `True` for cookie auth |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Must include the scheme (`https://app.example.com`) |

> **Deployment constraint.** `SameSite=Lax` cookies require the frontend and API
> to share a registrable domain (`app.kawaiibake.com` + `api.kawaiibake.com`).
> Locally `localhost:3000 → :8000` is same-site, so a mismatch stays invisible
> until deploy. If a shared domain is not possible, switch the credential issuer
> to JWT rather than loosening cookies to `SameSite=None`.
