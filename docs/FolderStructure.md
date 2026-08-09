# KawaiiBake — Folder Structure

Django is **API-only**. Feature apps contain no page templates and no static
assets; the Next.js frontend owns all UI. See [ADR 0005](adr/0005-api-only-backend.md).

## Root Layout

```
KawaiiBake/
├── config/            # Settings, root URLs, WSGI/ASGI, Celery
├── apps/              # Feature apps — one app per domain
├── media/             # User uploads (git-ignored, later object storage)
├── ai/                # Framework-free AI package (providers, factory, use cases)
├── infrastructure/    # Adapters for external services (cache, email, storage, …)
├── docs/              # Documentation + ADRs
├── tests/             # Cross-app integration & e2e tests
├── scripts/           # Operational / maintenance scripts
├── docker/            # Dockerfile & compose files
├── requirements/      # Layered dependency files
├── manage.py
├── pyproject.toml     # ruff / pytest / coverage config
├── .env.example
└── .gitignore
```

There is **no** root `templates/` or `static/` directory. `staticfiles/` is a
build output for `collectstatic`, needed only by Django admin.

## Anatomy of a Feature App

Every layer that can grow is a **package** of small modules (~300 lines max).

```
apps/<feature>/
├── apps.py                  # AppConfig
├── admin.py
├── models/                  # or models.py while small
├── managers.py
├── constants.py             # TextChoices enums, limits, magic values
├── exceptions.py            # DomainError subclasses (code + status_code)
├── utils.py
│
├── services/                # business logic; no request, no HTTP
├── repositories/            # write-side ORM
├── selectors/               # read-side ORM + redacted DTOs
├── validators/              # domain rules
├── permissions/             # authorization, as pure functions
├── tasks/                   # Celery
├── signals/                 # receivers (kept empty by preference)
│
├── api/                     # ← the HTTP layer
│   ├── serializers/         # message shape only
│   ├── views/               # thin: validate → service → serialise
│   └── urls/
│
├── migrations/
├── tests/
└── templates/<feature>/emails/   # ONLY for server-rendered email bodies
```

Removed from the earlier MVT anatomy: `forms/`, `templates/<app>/{pages,components,partials}`,
`static/<app>/`, and top-level `serializers/` (superseded by `api/serializers/`).

**The one `forms/` exception** is `apps/users/forms/admin_forms.py`. A custom
user model requires admin creation and change forms — without them the admin
"Add user" page stores a plaintext password and the change form re-hashes the
existing hash.

## Implemented in Phase 1

### `apps/users`

```
apps/users/
├── models/       user.py · profile.py (favorite_categories = M2M to the
│                 taxonomy since Phase 14) · preference.py (locale th/en)
├── managers.py                       # UserManager — creates all three rows atomically
├── constants.py                      # BakingExperienceLevel, PreferredLanguage,
│                                     # ProfileVisibility, DietaryRestriction, Theme,
│                                     # RESERVED_USERNAMES, avatar limits
│                                     # (BakingCategory: historical, migrations only)
├── exceptions.py                     # EmailAlreadyRegistered, ProfileNotVisible, …
├── admin.py + forms/admin_forms.py
├── repositories/ user_repository.py · profile_repository.py (atomic scalar+M2M)
├── selectors/    user_selector.py (MeDTO) · profile_selector.py
│                 (PublicProfileDTO · PersonalizationFact · profile_completion)
├── services/     user_service.py · profile_service.py (live-taxonomy validation)
├── validators/   user_validator.py · profile_validator.py
├── permissions/  profile_permissions.py
├── api/
│   ├── serializers/  user · profile · preference · settings_serializers.py
│   ├── views/        profile_views.py · preference_views.py · account_views.py
│   │                 · settings_views.py (read-only composition)
│   └── urls/         __init__.py (/users/…) · me.py (/me/settings/)
└── tests/        test_models · test_selectors · test_services · test_api
                  · test_personalization (Phase 14)
```

### `apps/authentication`

Owns **no models** — see `models.py` for why.

```
apps/authentication/
├── auth_backends/  email_backend.py · oauth_backend.py (stub)
├── tokens/         password_reset_token.py · email_verification_token.py
├── services/       registration · login · password_reset · email_verification
│                   + oauth_service.py, mfa_service.py (documented stubs)
├── validators/     registration_validator.py · password_reset_validator.py
├── permissions/    rate_limit_permissions.py
├── tasks/          email_tasks.py
├── constants.py    exceptions.py    utils.py
├── api/
│   ├── credentials/    base.py · session_issuer.py · jwt_issuer.py (stub)  ← the auth seam
│   ├── authentication.py                                     # CsrfEnforcedSessionAuthentication
│   ├── schema.py                                             # OpenAPI auth extension
│   ├── serializers/  auth_serializers.py
│   ├── views/        session_views.py · password_views.py · verification_views.py
│   └── urls/
├── templates/authentication/emails/  verify_email.txt · password_reset.txt · password_changed.txt
└── tests/            test_tokens · test_services · test_api
```

### `apps/recipe_categories` (Phase 2)

A deliberate leaf: it never references `recipes`.

```
apps/recipe_categories/
├── models/category.py · constants.py · exceptions.py · admin.py
├── repositories/category_repository.py
├── selectors/category_selector.py     # ref_queryset · list_categories · resolve_slugs
│                                      #   ← the public read API other apps call
├── services/category_service.py
├── api/serializers/ · api/views/ · api/urls/
└── migrations/  0001_initial · 0002_seed_from_baking_category
```

### `apps/recipes` (Phase 2)

```
apps/recipes/
├── models/     recipe.py · ingredient.py · step.py · image.py · nutrition.py
├── constants.py    # RecipeStatus, RecipeVisibility, RecipeScope, Difficulty,
│                   # Unit, Ordering + ORDERING_MAP, limits, RESERVED_RECIPE_SLUGS
├── exceptions.py · utils.py           # build_slug_base, normalize_ingredient_name (pure)
├── repositories/  recipe_ · ingredient_ · step_ · image_ · nutrition_repository.py
├── selectors/
│   ├── recipe_visibility.py           # the Q builders — single source of truth
│   ├── recipe_filters.py              # RecipeListFilters (frozen dataclass)
│   └── recipe_selector.py             # list · detail · list_by_ids (future recommendation)
├── services/   recipe_ · ingredient_ · step_ · publish_ · image_ · nutrition_service.py
├── validators/ recipe_ · ingredient_ · step_ · publish_ · image_ · nutrition_validator.py
├── permissions/recipe_permissions.py  # pure predicates: edit / delete / change status
├── api/
│   ├── serializers/  recipe_serializers.py · recipe_write_serializers.py
│   │                 · filter_serializers.py
│   ├── views/        recipe_views.py · search_views.py · publish_views.py · image_views.py
│   └── urls/                          # literals BEFORE <str:slug>
└── tests/  test_visibility · test_models · test_services · test_api
         · test_list_search · test_images_nutrition · factories.py
```

### Shared

```
apps/core/
├── models/base.py          TimeStampedModel
├── exceptions.py           DomainError, RateLimitedError  (framework-free)
└── middleware/request_logging.py   RequestIDMiddleware

apps/common/
├── api/  exception_handler.py · views.py · serializers.py · pagination.py
│      (error envelope; ServiceAPIView / CsrfProtectedAPIView /
│       PaginatedServiceAPIView; StrictSerializer; DefaultPageNumberPagination)
└── validators/image_validator.py    # shared byte-level image check, used by
                                     # both users (avatars) and recipes

infrastructure/
├── cache/    base.py + redis_cache.py      (rate limiting)
├── email/    base.py + smtp_email.py
├── storage/  base.py + local_storage.py + s3_storage.py (stub)
├── search/   base.py + simple_search.py (default, portable)
│                    + postgres_search.py (pg_trgm; not covered by tests)
├── logging/  config.py
└── queue/                                  (stub)
```

## AI Package (real since Phase 7 — framework-free)

No Django import anywhere in the package; the assistant app passes
configuration in as plain values and data crosses as frozen dataclasses.

```
ai/
├── factory.py       build_provider(name, config) — registry, one entry per backend
├── schemas.py       AIMessage · AICompletion (the boundary types)
├── constants.py     provider + role names
├── exceptions.py    AIProviderError family (plain Exception — no HTTP here)
├── providers/       base.py (AIProvider interface)
│                    · mock.py (deterministic echo — the dev/CI default)
│                    · openai.py (stdlib HTTP, base_url covers local runtimes)
│                    · gemini.py · anthropic.py · ollama.py (stubs)
├── chatbot/  recommendation/  embeddings/  vector_store/        (stubs —
├── prompt_templates/  ingredient_substitution/  image_analysis/  future phases)
```

### `apps/courses` (Phase 3)

A leaf toward `lessons`: never imports it, never touches `course.lessons`.

```
apps/courses/
├── models/     course.py (published_lesson_count — the boundary made physical)
│               · enrollment.py (one row per user+course, forever)
├── selectors/  course_visibility.py (Q builders with a `prefix` param,
│               composable across joins) · course_selector.py (CourseRef)
│               · enrollment_selector.py (EnrollmentRef.grants_access)
├── services/   course_service.py (incl. sync_published_lesson_count)
│               · enrollment_service.py (idempotent enroll, soft drop,
│                 record_course_completion) · publish_service.py
├── repositories/ · validators/ · permissions/ · api/{serializers,views,urls}/
└── tests/      test_visibility (matrix incl. archived-but-enrolled)
                · test_services · test_enrollment · factories.py
```

### `apps/lessons` (Phase 3; progress extracted in Phase 6)

The dependent side: imports courses' public selectors/services only. Learner
state moved to ``apps/progress`` in Phase 6 (ADR 0012) — this app is pure
content now.

```
apps/lessons/
├── models/     lesson.py (entity — never collection-replaced; recipe + quiz FKs)
├── repositories/ lesson_repository.py — the single mutation choke point and
│               sole caller of the counter sync
├── selectors/  lesson_selector.py (composes course visibility via prefix Q;
│               LessonRef + list_published_refs = the public API progress uses)
├── services/   lesson_service.py (two-layer 404/403 gate, reorder validation)
├── api/        views/{lesson_views,course_nested_views}.py
│               · urls/{__init__,course_nested}.py — the nested urlconf is
│                 mounted under /api/v1/courses/ by config, not by coupling
├── management/commands/recount_lessons.py
└── tests/      test_visibility_gate (the 404/401/403/200 matrix)
                · test_lessons (counter, reorder, N+1) · test_quiz_link
```

### `apps/progress` (Phase 6)

Learner state, extracted from lessons: ``progress → lessons → courses``,
and no content app knows this one exists.

```
apps/progress/
├── models/     lesson_progress.py (completed_at nullable = the flag;
│               first_completed_at stamped once, survives un-completing)
│               · course_progress.py (no counters — completed_at only,
│                 stamped once by conditional UPDATE)
│               · activity.py (append-only day-facts; unique
│                 (user, date, type) = idempotent streak substrate)
├── repositories/ progress_repository.py
├── selectors/  progress_selector.py (grouped aggregates — flat query count)
├── services/   progress_service.py (complete/uncomplete/recalculate;
│               write-through + self-healing read, both through
│               recalculate_course_progress)
├── api/        urls/{lesson_nested,course_nested,me}.py — mounted under
│               /api/v1/lessons/, /api/v1/courses/ and /api/v1/me/ by config
└── tests/      test_progress.py (ported Phase 3 assertions + Phase 6 rules)
```

### `apps/questions` (Phase 4)

A strict leaf — the reusable question bank. Imports no feature app; knows
nothing of quizzes, attempts or scores.

```
apps/questions/
├── models/     question.py (frozen_at — the lifecycle state this app owns;
│               version + supersedes = versioning prep) · answer_choice.py
│               (is_correct is a per-field secret) · tag.py
├── repositories/ question_repository.py — home of freeze() (idempotent,
│               monotonic) and acquire_edit_gate() (the optimistic
│               conditional UPDATE that doubles as the row lock)
├── selectors/  question_selector.py (TakerQuestionDTO — structurally no
│               is_correct) · answer_key.py (the ONE key read path; only
│               quiz scoring may import it) · question_filters.py
├── services/   question_service.py (freeze_questions — public cross-app API)
├── validators/ question_validator.py (per-type choice rules, used at write
│               time AND by the quizzes publish gate)
├── permissions/ · api/{serializers,views,urls}/
└── tests/      test_services (freeze matrix) · test_api · factories.py
```

### `apps/quizzes` (Phase 4)

The dependent side: composes bank questions by reference, owns attempts and
scoring.

```
apps/quizzes/
├── models/     quiz.py · quiz_question.py (composition — nothing references
│               it, so collection-replace is safe here) · attempt.py
│               (denormalized results; one open attempt per user+quiz)
│               · attempt_answer.py (the start-time snapshot rows)
├── selectors/  quiz_visibility.py (Q builders + archived-but-attempted
│               branch) · quiz_selector.py (QuizRef) · attempt_selector.py
│               · quiz_filters.py
├── services/   quiz_service.py · publish_service.py · attempt_service.py
│               (start = freeze + snapshot in ONE transaction)
│               · scoring_service.py (pure; grader registry per type)
├── repositories/ quiz_repository.py · attempt_repository.py (one-shot
│               conditional submit transition)
├── management/commands/refreeze_questions.py   # rebuilds frozen_at drift
├── validators/ · permissions/ · api/{serializers,views,urls}/ · utils.py
└── tests/      test_visibility · test_services · test_attempts (snapshot +
                leak sweep) · test_scoring · factories.py
```

### `apps/reviews` (Phase 5)

Dependent side toward both content apps: explicit two-FK targets (ADR 0011).

```
apps/reviews/
├── models/     review.py (nullable recipe/course FKs, exactly-one check;
│               partial unique per target on ACTIVE rows; status
│               active/hidden/deleted — nothing hard-deletes)
├── selectors/  review_selector.py · rating_selector.py (computed stats +
│               the future caching seam — no stored rating columns)
├── services/   review_service.py (target resolution via public refs,
│               own-content block, moderation split)
├── repositories/ · validators/ · permissions/
├── api/        urls/{__init__,recipe_nested,course_nested}.py — nested
│               routes mounted under the content prefixes by config
└── tests/      test_services · test_api (incl. assertNumQueries guard)
```

### `apps/favorites` (Phase 5)

```
apps/favorites/
├── models/     favorite.py (same target shape, no status — a toggle;
│               hard-deleted on unfavorite)
├── selectors/  favorite_selector.py — composes BOTH content apps' detail
│               visibility via prefix Q builders in one query
├── services/   favorite_service.py (idempotent toggle, fail-closed resolve)
├── repositories/
├── api/        urls/{recipe_nested,course_nested,me}.py — the list lives at
│               /users/me/favorites/, mounted by config
└── tests/      test_favorites.py
```

### `apps/assistant` (Phase 7)

Owns AI conversation state; content apps never import it. The only Django
consumer of the `ai/` package.

```
apps/assistant/
├── models/     conversation.py (explicit SET_NULL targets, context/type
│               check; prompt_version stamped once)
│               · message.py (append-only transcript — no updated_at,
│                 system role never stored)
│               · prompt_template.py (name × language × version; partial
│                 unique keeps one active)
│               · usage_log.py (append-only billing/quota ledger)
├── selectors/  conversation_selector.py (owner-scoped reads, provider
│               replay window) · prompt_selector.py (active vs stamped)
├── services/   conversation_service.py (context validation + prompt stamp)
│               · message_service.py (two-transaction send; provider-error
│                 translation) · context_service.py (strict-at-creation /
│                 lenient-at-send loading via public content APIs)
├── repositories/ conversation_repository.py (append-only writes)
├── permissions/  rate_limit_permissions.py (per-user send throttle)
├── validators/   message_validator.py (length + normalisation)
├── api/        urls/{__init__,me}.py — /assistant/… plus
│               /me/assistant/conversations/, mounted by config
├── migrations/ 0001_initial · 0002_seed_prompt_templates (version "1",
│               th + en, all four context types)
└── tests/      test_models (Thai round-trip, constraints) · test_services
                · test_providers · test_api (incl. assertNumQueries guard)
```

### `apps/certificates` (Phase 8)

Pure consumer of stamped facts: reads completion from progress, resolves
courses through refs; no content app imports it. Not gamification.

```
apps/certificates/
├── models/     certificate.py (immutable record — number, dates, printable
│               snapshot; partial unique keeps one active per (user, course);
│               revoked rows remain) · achievement.py (append-only facts,
│               unique per (user, type)) · badge.py (system-owned bilingual
│               presentation, no CRUD API)
├── selectors/  certificate_selector.py (owner scopes + the one public
│               token lookup)
├── services/   certificate_service.py (issue_if_completed — 404→403→409
│               gate, trusts progress; revoke; verify_token)
│               · achievement_service.py (award / recalculate — pull-based,
│                 no signals)
├── repositories/ certificate_repository.py (number allocation with
│               savepoint retry; stamp-once revoke; idempotent award)
├── api/        urls/{__init__,course_nested,me}.py — issue nested under
│               courses/, lists under me/, anonymous verify at
│               /certificates/<uuid>/, mounted by config
├── migrations/ 0001_initial · 0002_seed_badge_definitions (5 badges, th+en)
└── tests/      test_models · test_services · test_api (incl.
                assertNumQueries guards)
```

### `apps/gamification` (Phase 9)

Owns no facts — a pure consumer of four domains' public selectors. The
scaffold's `signals/` directory was deleted on principle.

```
apps/gamification/
├── models/     xp_transaction.py (append-only ledger — the only truth)
│               · user_level.py (recomputed aggregate for the leaderboard
│                 sort) · streak.py (derived from progress' activity days)
├── selectors/  gamification_selector.py (ledger counts/sums, leaderboard
│               queryset with the one join)
├── services/   xp_service.py (XP_RULES + award + pull-based recalculate)
│               · level_service.py (pure progressive curve)
│               · streak_service.py (full-history derivation, never
│                 incremented) · leaderboard_service.py
├── repositories/ gamification_repository.py (append + total-row rebuilds)
├── api/        urls/{__init__,me}.py — /leaderboard/ (public) plus
│               /me/gamification/, /me/streak/, mounted by config
├── migrations/ 0001_initial
└── tests/      test_services (curve, reconciliation, streak calendar)
                · test_api (incl. leaderboard assertNumQueries)
```

### `apps/notifications` (Phase 10)

A push sink: producers (reviews, courses, certificates) call its public
service post-commit; it imports no content domain. No repository — the
writes are one create and two conditional UPDATEs (guideline #15).

```
apps/notifications/
├── models/     notification.py (content-free snapshot; stamp-once read_at;
│               feed + unread indexes) · preference.py (per-event opt-out;
│               absent row = enabled)
├── selectors/  notification_selector.py (owner-scoped feed, live unread
│               count, effective preference map)
├── services/   notification_service.py (notify → on_commit → best-effort
│               _deliver; event wrappers; read stamps; preference upsert)
├── api/        serializers/ · views/ · urls/ — mounted at
│               /me/notifications/ by config; no create endpoint exists
├── migrations/ 0001_initial
└── tests/      test_models (incl. the no-content-FK guard) · test_services
                (commit/rollback + swallow contracts) · test_integration
                (the three producer wires) · test_api (incl.
                assertNumQueries + privacy sweeps)
```

### `apps/gallery` (Phase 11)

User showcases. Dependent side toward recipes/courses (public-listing
reference validation); the repository exists for one job — rows and
stored files must never drift apart.

```
apps/gallery/
├── models/     post.py (two-state status; SET_NULL references)
│               · image.py (position-ordered, storage-backed)
├── selectors/  gallery_visibility.py (the one Q) · gallery_selector.py
├── services/   gallery_service.py (reference validation, exact-set
│               reorder, capacity)
├── repositories/ gallery_repository.py (file-safe create/delete/reorder)
├── validators/ gallery_validator.py (byte-level image checks)
├── api/        serializers/ · views/ (multipart upload endpoints) · urls/
└── tests/      test_gallery (lifecycle + cleanup) · test_api (incl.
                assertNumQueries + privacy)
```

### `apps/qa` (Phase 11)

Community Q&A — **not** `apps/questions` (the quiz item bank; ADR 0017
§14). Threads soft-delete, answers hard-delete, notifications flow out
through the Phase 10 sink.

```
apps/qa/
├── models/     thread.py (SET_NULL targets, at-most-one check,
│               accepted_answer FK) · answer.py
├── selectors/  qa_visibility.py (one prefix-parameterised Q)
│               · qa_selector.py
├── services/   thread_service.py (create/moderate/soft-delete/accept)
│               · answer_service.py (answer + notification wiring)
├── api/        serializers/ · views/ · urls/ — /api/v1/qa/threads/…
└── tests/      test_services (visibility, accepted invariant,
                notifications) · test_api (incl. assertNumQueries)
```

### `apps/recommendation` (Phase 12)

A pure consumer with **no models, no migrations, no admin** — the first
app whose folder anatomy is defined by what it deliberately lacks
(ADR 0018). Substitution rules are code, not rows.

```
apps/recommendation/
├── constants.py    every scoring weight + reason code, named — ranking
│                   policy is a one-file diff
├── exceptions.py   its own RecipeNotFoundError (ADR 0008)
├── rules/          substitution_rules.py — the rule registry + aliases
│                   behind a lookup() seam (future catalogue boundary)
├── services/       scoring_service.py (pure: score/rank/diversify,
│                   injected now) · recommendation_service.py
│                   (gather signals → candidates → score → rank)
│                   · substitution_service.py
├── api/            serializers/ · views/ (cards stitched from the
│                   content apps' own serializers) · urls/
│                   (+ urls/recipe_nested.py for …/substitutions/)
└── tests/          test_scoring (pure + registry integrity)
                    · test_recommendations (personalization, cold start,
                    eligibility, assertNumQueries) · test_substitutions
```

### `apps/rewards` (Phase 13)

The economy: a materialized account, an immutable ledger, pull-based
earning keyed to identified facts (ADR 0019).

```
apps/rewards/
├── constants.py    RewardKind/RewardReason · REWARD_RULES (points) ·
│                   REASON_TEXT (authored Thai + English) · event_key()
├── exceptions.py   insufficient_balance (409) · invalid_amount ·
│                   reason_required · not_found
├── models/         account.py (PK-as-FK, materialized balance +
│                   lifetime totals) · transaction.py (append-only,
│                   UNIQUE (account, event_key), CHECK amount ≠ 0)
├── repositories/   reward_repository.py — the single write path:
│                   conditional-UPDATE debits + savepoint idempotency
├── selectors/      reward_selector.py (owner-scoped reads,
│                   ledger_totals for reconciliation)
├── services/       reward_service.py (claim/spend/adjust + summary)
├── management/     commands/reconcile_rewards.py (dry-run default,
│                   --apply repairs: append + recompute only)
├── api/            serializers/ · views/ · urls/ (me.py → /me/rewards/…,
│                   __init__.py → /rewards/adjustments/ staff-only)
└── tests/          test_economy (atomicity, races, guards) · test_rules
                    (registry + Thai) · test_api · test_reconcile
```

## Not Yet Implemented

Three feature-app stubs remain and are **not** in `INSTALLED_APPS`:
`dashboard`, `adminpanel`, plus two superseded ones due for deletion —
`chatbot` (replaced by Phase 7's `assistant`) and `achievements`
(replaced by Phase 8's `certificates`). The MVT-era `forms/`,
`templates/` and `static/` directories in these stubs should be pruned
when each app is implemented, as was done in Phases 2–5 and 9–12.
