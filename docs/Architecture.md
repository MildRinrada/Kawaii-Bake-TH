# KawaiiBake  Architecture

## 1. Overview

KawaiiBake is a **separated frontend/backend** system:

- **Django + DRF** owns the database, business logic, authentication,
  authorization, background work and AI integration. It serves JSON only.
- **Next.js + TypeScript + React + Tailwind** owns every page, component,
  interaction and animation.

Django renders no pages and ships no frontend assets. Templates and staticfiles
remain enabled for exactly two reasons: **Django admin**, and **server-rendered
email bodies**.

The backend is organised as feature apps under `apps/`, each a vertical slice
owning its models, business logic, data access and API surface.

## 2. Guiding Principles

- **Clean Architecture**  dependencies point inward: API → services →
  repositories/selectors → ORM. Vendors sit behind `infrastructure/` and `ai/`.
- **SOLID / high cohesion, low coupling**  a feature owns everything about
  itself and knows nothing of another feature's internals.
- **DRY**  shared code lives only in `apps/core`, `apps/common`, `infrastructure/`.
- **KISS**  no layer is added unless it removes complexity elsewhere.

## 3. Layered Flow

```
HTTP request (from Next.js)
    │
    ▼
api/urls/            route table
    │
    ▼
api/views/           thin: validate shape → call service → serialise
    │  ├─ api/serializers/   message shape only (no ORM, no .save())
    │  └─ permissions/       authorization, as pure functions
    ▼
services/            business logic; NO request, NO HttpResponse
    │  ├─ validators/        domain rules
    │  ├─ repositories/      write-side ORM
    │  ├─ selectors/         read-side ORM (+ redacted DTOs)
    │  ├─ tasks/             Celery
    │  ├─ infrastructure/    cache, email, storage, queue
    │  └─ ai/                AI use cases
    ▼
models.py            schema only
```

### Hard rules

1. Views contain no business logic and issue no queries.
2. Services never touch `request`, never render, never return HTTP objects.
3. Repositories and selectors are the only place ORM queries live.
4. Cross-app calls go through the other app's public **service/selector** API 
   never its models or repositories. (`apps.authentication` writes user state
   through `apps.users.services.user_service`.)
5. Vendor SDKs appear only in `infrastructure/` and `ai/providers/`.

### DRF conveniences that are banned

Each of these executes ORM inside the HTTP layer and would quietly dissolve
rule 3:

- `ModelSerializer` for writes
- `serializer.save()` / `create()` / `update()`
- `queryset` or `get_object()` on views
- `UniqueValidator`, `PrimaryKeyRelatedField(queryset=…)`, `SlugRelatedField`
- traversing un-prefetched relations in an output serializer

Plain `APIView` throughout. Even for the paginated recipe list, `GenericAPIView`
is **not** used: it ships `queryset` and `get_object()`, the two banned
attributes, and inheriting them while promising not to use them is the slow
dissolution this section warns about. Instead `apps/common/api/views.py` defines
`PaginatedServiceAPIView`, which exposes only `paginated_response(queryset,
serializer_class)`  it paginates a **selector's** lazy queryset, so the ORM
executes at the edge and nowhere else.

`django-filter` is likewise rejected: its standard wiring requires
`view.queryset`, and `ModelChoiceFilter(queryset=…)` is the same violation as
the already-banned `PrimaryKeyRelatedField(queryset=…)`. Query strings are
parsed by a `StrictSerializer` into a frozen filter dataclass instead  and
because it is strict, `?catgeory=cake` returns 400 rather than silently
returning everything.

**Viewer identity never travels inside the filter object.** It is a separate
argument to the selector, so nothing a client can put in a query string can
influence who the server thinks is asking.

**Serializer vs `validators/`:** the serializer validates the *message*
(presence, type, length, choice membership); `validators/` validates the
*domain* (reserved handles, age limits, image bytes, uniqueness). Domain rules
run inside services so they hold for every caller, not just HTTP.

## 4. The Credential Seam

Authentication splits into two halves that must not be merged:

| Half | Location | Nature |
|---|---|---|
| *Are these credentials valid?* | `services/login_service.py` | Request-free, unit-testable |
| *How does the client prove it later?* | `api/credentials/` | Irreducibly request-bound |

`api/credentials/` is the **only** place `django.contrib.auth.login`/`logout`
may be imported, and the only place a future JWT library may be. It implements
a `CredentialIssuer` protocol; `settings.AUTH_CREDENTIAL_ISSUER` selects the
implementation.

```
LoginView.post()
  → LoginSerializer                       shape
  → login_service.authenticate_user()     primitives in, User or domain error out
  → get_credential_issuer().issue()       session cookie today, JWT tomorrow
  → Response({status, user, **body})
```

Phase 1 ships `SessionCredentialIssuer`. Adding JWT means writing
`jwt_issuer.py` and changing one setting  no view, serializer, service,
repository, selector or URL changes. See [ADR 0007](adr/0007-session-auth-for-phase-1.md).

Two details make the seam hold: `login()` is always called with an explicit
`backend=` (so adding an OAuth backend cannot break it), and the
`IssuedCredential.status` field already exists (so adding 2FA is additive
rather than a breaking response-shape change).

## 5. Error Handling

Services raise `DomainError` subclasses carrying their own `code` and
`status_code`. `apps/core/exceptions.py` is framework-free  services must never
import DRF. A single `EXCEPTION_HANDLER` in `apps/common/api/` renders the
envelope, so **no view contains `try`/`except`**.

It also normalises two DRF behaviours: `NotAuthenticated` becomes **401** (DRF
would return 403 under session auth, and frontends branch on 401), and
unexpected exceptions are logged with a traceback but returned as a generic
`internal_error`.

## 6. Visibility Fails Closed

Two different shapes of the same principle, chosen to match what each domain
actually needs.

**Per-field redaction (users).** Public profiles are not serialised from a
model: `profile_selector` builds a `PublicProfileDTO` with the owner's privacy
settings already applied, so the API layer cannot reach a hidden field.
Conditional logic inside a serializer would fail *open*  the next field added
would leak by default.

**Row-level visibility (recipes).** A recipe has no per-field privacy: you see
all of it or you get 404, so the DTO's rationale does not transfer and a DTO
would be allocation without safety. What replaces it is
`selectors/recipe_visibility.py`, which exports the `Q` builders that **both**
the list and the detail path use. A boolean `can_view_recipe()` beside a
separate list filter would be one rule with two implementations, and two
implementations drift. Guarantees:

- there is deliberately **no** "all recipes" selector, so nothing can bypass them;
- both builders default to an anonymous, non-staff viewer;
- callers only ever `.filter()` further, and a filter can only narrow.

The guarantee a DTO would have given up is replaced by a test:
`assertNumQueries(3)` on the list endpoint, written before the serializer. It is
the only thing that catches a future `SerializerMethodField` walking an
un-prefetched relation.

Enforcement for recipes is a single parametrised test over the full cartesian
product  3 statuses × 3 visibilities × 4 viewer classes × 2 endpoints.

In both domains, hidden and non-existent return the same **404**. A 403 would
confirm the resource exists.

## 7. Cross-Cutting Packages

- **`apps/core/`**  abstract base models, `DomainError`, request-id middleware.
- **`apps/common/`**  domain-agnostic HTTP plumbing: the exception handler,
  `ServiceAPIView` / `CsrfProtectedAPIView`, `StrictSerializer`.
- **`infrastructure/`**  external services behind interfaces: `cache/`
  (rate limiting), `email/`, `storage/`, `queue/`, `search/`, `logging/`.
  Business logic depends on the interface, never the vendor. `search/` follows
  the same shape: its backends take and **return a queryset without executing
  it**, so search composes with the visibility `Q`, further filters and
  pagination. An interface returning matching ids would force a two-query
  `IN (...)` pattern that breaks all three.
- **`ai/`**  framework-free (no Django import anywhere in it); `providers/`
  holds backend adapters behind one `AIProvider` interface, `factory.py`
  resolves one by name. Real since Phase 7: the assistant app reads
  `AI_PROVIDER` from settings and passes plain values in  data crosses the
  boundary as frozen dataclasses (`AIMessage`/`AICompletion`), never models.
  The default provider is a deterministic offline mock, so development and
  CI need no API key; the OpenAI adapter takes a `base_url`, which also
  covers OpenAI-compatible local runtimes. Provider failures raise the
  package's own plain exceptions; the assistant translates them to its
  `AssistantUnavailableError` (503) at the boundary  the ADR 0008 rule
  applied to a non-Django callee. One hard rule inherited from the error
  seam: **no database transaction ever spans a provider call** (the user's
  message commits before the network is touched; the reply commits after).
  See ADR 0013.

## 8. CSRF, CORS and Cookies

DRF wraps every `APIView` in `csrf_exempt`, and `SessionAuthentication` enforces
CSRF only for *already authenticated* requests. Unauthenticated POST endpoints
(`/login/`, `/register/`, `/password-reset/`) would therefore be unprotected,
enabling login-CSRF. They inherit `CsrfProtectedAPIView`, which applies
`csrf_protect` explicitly. This is covered by a test.

`CSRF_COOKIE_HTTPONLY = False` is required and safe: the double-submit token
must be secret from *other origins*, not from our own JavaScript.

## 9. Background Work

Celery + Redis. Each app declares tasks in `tasks/`. Auth emails are sent from
tasks, and tokens are minted **inside** the task so no credential is written to
the broker. Development and test settings run tasks eagerly, so no broker is
needed locally while still exercising the production code path.

## 10. Settings

`config/settings/` splits `base` / `development` / `production` / `testing`.
Secrets come from environment variables. Development defaults to SQLite so the
project runs without PostgreSQL; production requires it.

## 11. Scalability

| Concern | Approach |
|---|---|
| 100k+ users | Selectors are the single seam for caching and query tuning; `cached_db` sessions in production |
| Auth abuse | Cache-backed rate limiting, keyed by IP + email  no tables |
| Heavy AI | Per-app Celery tasks on dedicated queues |
| Image uploads | `infrastructure/storage` adapter swap to S3  no migration, because model fields resolve storage through a callable |
| Mobile app | Reuses the same services behind the same API |
| Microservices | App boundaries plus infrastructure adapters are ready-made extraction seams |

## 12. Cross-App Relationships

A lazy string model reference (`ManyToManyField("recipe_categories.RecipeCategory")`)
is a schema declaration and creates no Python import edge  the same mechanism as
`settings.AUTH_USER_MODEL`. An `import` is a code dependency and remains banned.
The dependent app owns the relation, so the referenced app stays a leaf.
Details and the exact permitted/forbidden list are in
[ADR 0008](adr/0008-cross-app-model-references.md).

Phase 3 stress-tested the rule with the deeply entangled courses/lessons pair
and produced four reusable mechanisms ([ADR 0009](adr/0009-courses-lessons-boundary.md)):

1. **Counter push**  when app A's invariant needs a count of app B's rows,
   B pushes a rebuildable counter into A's own column through A's public write
   API, inside B's mutation transaction (`Course.published_lesson_count`).
2. **Prefix-parameterised Q builders**  A exports its visibility rule as
   `visible_q(prefix="course__")` so B applies the identical rule across a
   join, keeping one implementation.
3. **Frozen refs**  cross-app reads return dataclasses (`CourseRef`,
   `EnrollmentRef`), never model instances.
4. **Write-through + self-healing read**  cross-boundary state changes
   (course auto-completion) are explicit service calls in the allowed
   direction, with the read path re-checking to close write races. No signals.

The lesson content gate also established the one carve-out from "hidden ⇒
404": when a resource's **existence is already public** (the syllabus lists
it), denying access uses **403 with a stable code** (`enrollment_required`) 
reachable only after the 404 existence layer has passed.

Phase 4 (`quizzes → questions`, [ADR 0010](adr/0010-question-bank-and-quiz-boundary.md))
reused mechanisms 1–3 and added two refinements:

- **Counter push carries any monotonic state, not just numbers.**
  `Question.frozen_at` is pushed by quizzes at attempt start exactly as the
  lesson counter is pushed  the owner records *that*, the pusher knows *why*
   and enforced by an optimistic conditional UPDATE
  (`WHERE frozen_at IS NULL`) whose gate write doubles as the row lock, so no
  `select_for_update` is needed. The rebuild command
  (`refreeze_questions`) lives with the app that owns the *reason*.
- **Snapshot completeness.** When one app records outcomes derived from
  another app's mutable data (grading against bank questions), the recording
  app snapshots **everything** grading needs at the moment of commitment
  (attempt start): question set, order, `points_possible`, `max_score`  and
  the referenced rows are frozen in the same transaction. After that moment,
  the outcome path reads nothing mutable, which is also what makes the
  Phase 2 collection-replace pattern safe for `QuizQuestion` (nothing
  references composition rows).

Phase 4 also produced a second structural-secret pattern beside the users
DTO: the quiz taker payload is built from DTOs that **lack** `is_correct`,
and the full answer key lives in one screaming-name module
(`questions/selectors/answer_key.py`) whose only legitimate caller is
scoring.

Phase 6 (`progress` → `lessons` + `courses`,
[ADR 0012](adr/0012-progress-domain.md)) established the **domain
extraction** precedent: learner state moved out of `lessons` into its own
app once it became a growth point, with the content apps ending the phase
knowing nothing about it  the syllabus lost its progress merge, and the
progress routes are mounted under the content prefixes by config. Course
completion remains write-through + self-healing (mechanism #4), now
funneled through one function in the owning domain, and the append-only
`LearningActivity` ledger separates immutable facts from mutable state.

Phase 5 (`reviews`/`favorites` → `recipes` + `courses`,
[ADR 0011](adr/0011-review-target-architecture.md)) settled how one app
points at **several** content types: explicit nullable FKs with an
exactly-one check constraint  never a `GenericForeignKey`, chiefly because
a GFK cannot be joined and therefore cannot compose the prefix-parameterised
visibility Q builders that every read path here is built on. The favorites
list is the mechanism's showcase: it filters
`recipe_visible_q(prefix="recipe__") | course_visible_q(prefix="course__")`
in one query, which is why a private recipe silently leaves its owner's
favorites while an archived course stays for its enrolled student  both
behaviours inherited from the content apps' own rules, not re-implemented.

Phase 7 (`assistant` → `recipes` + `lessons` + `courses`,
[ADR 0013](adr/0013-ai-assistant-foundation.md)) added the first app whose
core collaborator is **outside Django entirely**. Three refinements:

- **The context loader is a composition point, not a rule.** The assistant
  anchors conversations to content through the content apps' existing
  public read APIs  including, for gated lesson bodies, the lessons
  *service* that owns the 404/403 gate  and translates the callee's domain
  errors into its own at the boundary. Visibility logic gained zero new
  implementations.
- **Explicit-FK targeting with SET_NULL.** The reviews target shape
  (ADR 0011) recurs, but with `SET_NULL` and a constraint that permits a
  NULL target: user history must outlive the content it discusses, and the
  read path degrades instead of erroring.
- **Versioned behaviour stamping.** `prompt_version` extends the
  stamp-once family (`published_at`, `completed_at`) from *state* to
  *behaviour*: a conversation permanently records which prompt shaped it,
  so operators can change the assistant without silently rewriting the
  ground old transcripts stood on.

Phase 8 (`certificates` → `progress` + `courses`,
[ADR 0014](adr/0014-certificates-and-achievements.md)) is the first
**pure consumer of another domain's stamped facts**: issuance trusts
`CourseProgress.completed_at` (progress' stamp-once write) and never
re-derives completion  the read-side counterpart of the counter-push
rule, with the same rationale (one implementation per invariant). Its
other contributions: the snapshot rule (ADR 0010) applied to an
*outward-facing paper record* (printable fields frozen at issuance, which
is what makes `SET_NULL` targets safe), a **two-key identity split** 
a human-facing sequential number that is never routable beside an
unguessable UUID that is the only lookup key  and pull-based awarding
(achievements are derived by certificates reading public facts, never
pushed by content apps, keeping the no-signals rule intact).

Phase 9 (`gamification` → `progress` + `certificates` + `quizzes` +
`reviews`, [ADR 0015](adr/0015-gamification-foundation.md)) completes the
consumer spectrum: an app that owns **no facts at all**, only an
append-only ledger derived from four other domains' facts plus two
recomputed aggregate rows. Its mechanisms:

- **Pull-based reconciliation.** `recalculate()` diffs monotonic fact
  counts (read via public selectors) against the ledger and appends only
  the difference  idempotent without locks, additive by construction,
  and requiring the producing domains to do *nothing* (not even the
  explicit push calls earlier phases used). The producers' append-only
  ledgers and stamp-once timestamps are what make this safe.
- **Total-rebuild aggregates.** `UserLevel`/`DailyStreak` are stored only
  for read performance and are overwritten wholesale from their sources
  on every change  the counter-push discipline (ADR 0009 #1) restated
  for internal state: a stored aggregate is acceptable exactly when its
  rebuild path is total.
- **The scaffold's `signals/` directory was deleted, not filled**  the
  no-signals rule survived its strongest temptation (a domain whose whole
  job is reacting to other domains' events) by not reacting at all.

Phase 10 (`reviews`/`courses`/`certificates` → `notifications`,
[ADR 0016](adr/0016-notifications-as-a-push-sink.md)) added the
complementary shape: a **push sink**. Where gamification pulls derived
aggregates ("how much, in total"), notifications receive event-time facts
("this just happened")  pushed by explicit producer service calls in the
allowed direction, because no later reconciliation can recover *when*
something happened or deliver it promptly. Its mechanisms:

- **Post-commit, best-effort delivery.** `notify()` registers with
  `transaction.on_commit`, so delivery can never join or precede the
  producer's transaction  no signal involved; and delivery is wrapped in
  a log-and-swallow boundary, so a notification failure structurally
  cannot fail a review, enrollment or award that already succeeded.
- **Content-free snapshot rows.** A notification stores text, not FKs 
  the reasoned inverse of ADR 0011: it joins nothing, and a content FK's
  only effect would be history-erasing CASCADEs. Producers pass every
  snapshot ingredient (including the actor's public handle), so the sink
  imports no domain at all.
- **Event vocabulary as governance.** A closed set of wired events;
  adding one is an ADR/docs change, which is what keeps a low-friction
  `notify()` call from becoming ambient spam coupling. (Phase 11 added
  the two Q&A events through exactly that door.)

Phase 11 (`gallery` + `qa` → `recipes`/`courses`,
[ADR 0017](adr/0017-community-gallery-and-qa.md)) added the community
layer and stress-tested the reference toolbox on user-generated content:

- **Deletion policy follows ownership of the words.** A gallery post is
  one author's artifact → hard delete with real media cleanup (files
  collected before the row cascade, removed after commit). A Q&A thread
  contains *other users'* answers → soft delete that no API surface ever
  returns again. Answers are single-author leaves → hard delete, with the
  thread's `accepted_answer` pointer healing via `SET_NULL`.
- **Public-reference validation.** A public artifact (gallery card) that
  joins and displays another domain's title may only reference content
  that is *publicly listed at creation*  checked through the content
  app's public listing selector, never a second visibility
  implementation.
- **Invariants by schema arithmetic.** "At most one accepted answer" is
  a single nullable FK column, so replacement is one UPDATE and
  unset-the-old is implicit  no constraint, no counter, nothing to
  repair.
- **`qa` beside `questions`.** Two domains sharing an English word stayed
  two apps: the assessment bank (secret answer keys, frozen history) and
  open discussion (public, moderated, socially accepted answers) have
  incompatible privacy postures  see ADR 0017 §14.

Phase 12 (`recommendation` → `recipes`/`courses`/`favorites`/`reviews`/
`users`, [ADR 0018](adr/0018-recommendation-and-substitution.md)) added
the widest pure consumer yet  five source domains, zero tables:

- **Derived, never stored.** Recommendations are computed per request
  from a bounded candidate pool at a pinned flat query count; the
  "no counters without a rebuild path" rule taken to its logical end 
  no stored state means nothing to rebuild.
- **Fact selectors, not model handouts.** Source apps export plain
  dataclass facts (`RecipeCandidateFact`, `RatingFact`,
  `PersonalizationFact`, …) through the Phase 9 additive-selector door;
  the consumer scores rows it could never join or mutate.
- **Broadcast surfaces use the anonymous listing rule.** A feed shown to
  everyone applies the source app's `visible_in_list_q()` with *no
  viewer*  stricter than the viewer's own rights, and still the source
  app's single implementation.
- **Determinism as an API contract.** No randomness, injected `now`,
  id-ascending tie-breaks, fixed reason-code order  same facts, same
  feed, in production and in tests.
- **A shared pure helper moves to `common` at its second consumer.**
  `normalize_ingredient_name` left `recipes.utils` (re-exported) the
  moment substitution needed the identical matching rule  one rule, one
  implementation, the prefix-Q discipline applied to plain functions.

Phase 13 (`rewards` → `progress`/`quizzes`/`certificates`,
[ADR 0019](adr/0019-rewards-economy.md)) added the economy  the Phase 9
pull boundary carrying money instead of reputation:

- **Identified facts, not counts.** The XP ledger reconciles *how many*;
  a currency reconciles *which ones*. Source apps grew identified-fact
  siblings of their count selectors (`completed_lesson_ids`, …), and
  every earning is keyed to one fact via a stable `event_key`.
- **Idempotency is a constraint, not a check.** `UNIQUE (account,
  event_key)` + savepoint-and-return-existing makes duplicate delivery
  economically inert under concurrency  the certificate-number retry
  pattern (ADR 0014) graduated into the write path itself.
- **Debits are conditional UPDATEs.** ``WHERE balance >= amount`` makes
  check-and-debit one statement; zero rows updated *is* the
  insufficient-funds answer, and `PositiveIntegerField`'s CHECK is the
  second net. No Python lock anywhere.
- **Corrections are entries.** Staff adjustments flow through the same
  atomic path with a required reason and an actor-handle snapshot 
  nothing ever assigns the balance column directly.
- **Bilingual reasons by registry.** A reason is a machine code plus
  authored Thai/English titles; a test rejects Thai titles containing no
  Thai. The badge precedent (ADR 0014) applied to an in-code registry.

Phase 14 (`users` ↔ the personalization consumers,
[ADR 0020](adr/0020-profile-personalization.md)) completed the profile
layer as the explicit-personalization source:

- **A migration promise kept.** The Phase 1 JSON category slugs became
  the planned M2M to `recipe_categories` by exact slug match  validation
  moved from a frozen enum to the live taxonomy, deleted categories
  self-heal by cascade, and the API shape never changed.
- **Explicit vs derived, physically separated.** `PersonalizationFact`
  carries only what the user *told* the system (experience, categories,
  language); behavioral taste stays in source domains and meets the
  explicit signal only inside the recommendation scorer.
- **One language field, one vocabulary.** `locale` is `th`/`en` with the
  set pinned equal to the assistant's  compatibility by construction,
  not by translation glue.
- **Composition without ownership.** `/me/settings/` is a GET-only
  stitch across users and notifications public boundaries; its
  `users.api → notifications.selectors` import is an API-edge consumer
  relationship that cannot cycle and cannot write.
- **Derived, not stored.** Profile completion is a pure function over
  intent-bearing fields  the no-counters rule applied to UX state.

## 13. Known Constraints

- **Cookie topology.** `SameSite=Lax` requires frontend and API to share a
  registrable domain. Locally this is invisible; if production splits them,
  switch the credential issuer to JWT rather than loosening the cookie.
- **No login audit table.** Sign-ins are logged, not queryable. See
  [Database.md](Database.md).
- **OAuth will need a table.** The "no unnecessary tables" rule cannot cover a
  provider link; that exception is recorded up front.
- **The layer rules are not yet machine-enforced.** Add `import-linter`
  contracts (`apps.*.api` must not import `django.db`; `apps.*.services` must
  not import `rest_framework`) before the team grows.
