# KawaiiBake  Database Design

## Implemented

| Phase | Tables |
|---|---|
| 1  Auth & users | `users_user`, `users_profile`, `users_preference` |
| 2  Recipes | `recipes_recipe`, `recipes_recipeingredient`, `recipes_recipestep`, `recipes_recipeimage`, `recipes_nutrition`, `recipe_categories_recipecategory`, plus the `recipes_recipe_categories` join table |
| 3  Learning | `courses_course`, `courses_enrollment`, `lessons_lesson`, `lessons_lessonprogress`, plus the `courses_course_categories` join table |
| 4  Assessment | `questions_question`, `questions_answerchoice`, `questions_questiontag`, `quizzes_quiz`, `quizzes_quizquestion`, `quizzes_quizattempt`, `quizzes_quizattemptanswer`, plus the `questions_question_tags` and `quizzes_quizattemptanswer_selected_choices` join tables |
| 5  Interaction | `reviews_review`, `favorites_favorite` |
| 6  Progress | `progress_lessonprogress` (moved from `lessons`), `progress_courseprogress`, `progress_learningactivity` |
| 7  AI assistant | `assistant_assistantconversation`, `assistant_assistantmessage`, `assistant_prompttemplate`, `assistant_aiusagelog` |
| 8  Certificates | `certificates_certificate`, `certificates_achievement`, `certificates_badgedefinition` |
| 9  Gamification | `gamification_xptransaction`, `gamification_userlevel`, `gamification_dailystreak` |
| 10  Notifications | `notifications_notification`, `notifications_notificationpreference` |
| 11  Community | `gallery_gallerypost`, `gallery_galleryimage`, `qa_questionthread`, `qa_questionanswer` |
| 12  Recommendation & substitution | **No tables  by decision.** Recommendations are derived per request from facts the other domains own; substitution rules live in an in-code registry keyed by `recipes_recipeingredient.normalized_name`. `recommendation_history`, `recommendation_score`, `user_interest`, `ingredient` and `ingredient_alias` were considered and rejected (ADR 0018 §9, §12) |
| 13  Rewards | `rewards_rewardaccount`, `rewards_rewardtransaction` |
| 14  Profile & personalization | No new model  `users.0002` executed the ADR 0006 plan: `users_profile.favorite_categories` (JSON slugs) became a real M2M to `recipe_categories` (join table `users_profile_favorite_categories`, backfilled by exact slug match, JSON column dropped), and `users_userpreference.locale` narrowed to the assistant-compatible `th`/`en` set with a Thai default |

Everything after those sections is a forward plan, not existing schema.

## Entity relationships

```
users_user ─1:N─▶ recipes_recipe          (related_name="recipes")
                     │
                     ├─M:N─▶ recipe_categories_recipecategory   (join owned by recipes)
                     ├─1:N─▶ recipes_recipeingredient           (related_name="ingredients")
                     ├─1:N─▶ recipes_recipestep                 (related_name="steps")
                     ├─1:N─▶ recipes_recipeimage                (related_name="images")
                     └─1:1─▶ recipes_nutrition                  (PK-as-FK, created lazily)

users_user ─1:1─▶ users_profile
users_user ─1:1─▶ users_preference

users_user ─1:N─▶ courses_course        (instructor, related_name="courses_taught")
users_user ─1:N─▶ courses_enrollment    (related_name="enrollments")
courses_course ─1:N─▶ courses_enrollment    (unique (user, course))
courses_course ─1:N─▶ lessons_lesson        (string ref; lessons is dependent)
courses_course ─M:N─▶ recipe_categories     (related_name="courses")
lessons_lesson ─N:1─▶ recipes_recipe        (nullable, SET_NULL  "this lesson
                                             teaches this recipe")

users_user ─1:N─▶ progress_lessonprogress   (related_name="lesson_progress")
users_user ─1:N─▶ progress_courseprogress   (related_name="course_progress")
users_user ─1:N─▶ progress_learningactivity (related_name="learning_activity")
lessons_lesson ─1:N─▶ progress_lessonprogress (unique (user, lesson))
courses_course ─1:N─▶ progress_courseprogress (unique (user, course))

users_user ─1:N─▶ questions_question   (author, related_name="questions")
users_user ─1:N─▶ quizzes_quiz         (owner, related_name="quizzes")
users_user ─1:N─▶ quizzes_quizattempt  (related_name="quiz_attempts")
questions_question ─1:N─▶ questions_answerchoice  (related_name="choices")
questions_question ─M:N─▶ questions_questiontag   (related_name="questions")
questions_question ─N:1─▶ questions_question      (supersedes, self-FK  versioning prep)
quizzes_quiz ─1:N─▶ quizzes_quizquestion     (CASCADE; unique (quiz, question))
quizzes_quizquestion ─N:1─▶ questions_question   (PROTECT  quizzes reference, never own)
quizzes_quiz ─1:N─▶ quizzes_quizattempt      (PROTECT  history blocks deletion)
quizzes_quizattempt ─1:N─▶ quizzes_quizattemptanswer (unique (attempt, question))
quizzes_quizattemptanswer ─N:1─▶ questions_question  (PROTECT  history pins the bank)
quizzes_quizattemptanswer ─M:N─▶ questions_answerchoice (selected_choices)
lessons_lesson ─N:1─▶ quizzes_quiz     (nullable, SET_NULL  reference only)

users_user ─1:N─▶ reviews_review       (related_name="reviews")
users_user ─1:N─▶ favorites_favorite   (related_name="favorites")
reviews_review ─N:1─▶ recipes_recipe   ┐ nullable FKs, CASCADE  exactly one
reviews_review ─N:1─▶ courses_course   ┘ set (check constraint, ADR 0011)
favorites_favorite ─N:1─▶ recipes_recipe ┐ same explicit-target shape;
favorites_favorite ─N:1─▶ courses_course ┘ plain uniques (NULL ≠ NULL)

users_user ─1:N─▶ assistant_assistantconversation (related_name="assistant_conversations")
users_user ─1:N─▶ assistant_aiusagelog            (related_name="ai_usage_logs")
assistant_assistantconversation ─1:N─▶ assistant_assistantmessage (CASCADE, append-only)
assistant_assistantconversation ─N:1─▶ recipes_recipe  ┐ nullable FKs, SET_NULL 
assistant_assistantconversation ─N:1─▶ lessons_lesson  │ at most the one matching
assistant_assistantconversation ─N:1─▶ courses_course  ┘ context_type (check constraint)

users_user ─1:N─▶ certificates_certificate  (related_name="certificates")
users_user ─1:N─▶ certificates_achievement  (related_name="achievements")
certificates_certificate ─N:1─▶ courses_course (nullable, SET_NULL  the
                                 printable snapshot outlives the course)
certificates_achievement ─N:1─▶ certificates_badgedefinition (PROTECT, nullable)

users_user ─1:N─▶ gamification_xptransaction (related_name="xp_transactions")
users_user ─1:1─▶ gamification_userlevel     (related_name="user_level")
users_user ─1:1─▶ gamification_dailystreak   (related_name="daily_streak")

users_user ─1:N─▶ notifications_notification (recipient,
                                              related_name="notifications")
users_user ─1:N─▶ notifications_notificationpreference
                                    (unique (user, event_type))
# Notification has NO other FK  rows are content-free snapshots (ADR 0016).

users_user ─1:N─▶ gallery_gallerypost   (related_name="gallery_posts")
gallery_gallerypost ─1:N─▶ gallery_galleryimage (CASCADE; files removed explicitly)
gallery_gallerypost ─N:1─▶ recipes_recipe ┐ nullable, SET_NULL  the showcase
gallery_gallerypost ─N:1─▶ courses_course ┘ outlives the content it names

users_user ─1:N─▶ qa_questionthread     (related_name="question_threads")
users_user ─1:N─▶ qa_questionanswer     (related_name="question_answers")
qa_questionthread ─N:1─▶ recipes_recipe ┐ nullable, SET_NULL  at most one
qa_questionthread ─N:1─▶ courses_course ┘ (check constraint)
qa_questionthread ─1:N─▶ qa_questionanswer      (CASCADE with the thread row;
                                                 threads soft-delete, so this
                                                 cascade never fires in practice)
qa_questionthread ─N:1─▶ qa_questionanswer      (accepted_answer, SET_NULL 
                                                 deleting the accepted answer
                                                 reverts the thread)
```

`recipe_categories` never references `recipes`: the many-to-many is declared on
`Recipe`, the dependent side, so the taxonomy remains a leaf that could ship
alone. See [ADR 0008](adr/0008-cross-app-model-references.md).

## Phase 1  Authentication & users

Exactly **three tables**.

### `users_user`

The account: credentials and authentication state only. Everything read on the
auth hot path stays here so session restore never needs a join.

| Column | Type | Notes |
|---|---|---|
| `id` | bigint PK | |
| `email` | varchar(254) unique | Login identifier, stored lowercased |
| `username` | slug(30) unique | Public URL handle |
| `password` | varchar | PBKDF2-SHA256 (Argon2 in production) |
| `is_active` | bool | Authentication kill-switch |
| `is_staff` / `is_superuser` | bool | Admin access, permissions |
| `is_email_verified` | bool | Address confirmed |
| `email_verified_at` | timestamptz null | |
| `deactivated_at` | timestamptz null | |
| `last_login` | timestamptz null | |
| `created_at` / `updated_at` | timestamptz | From `TimeStampedModel` |

Plus `groups` and `user_permissions` from `PermissionsMixin`.

**Constraints:** `UniqueConstraint(Lower("email"))` and
`UniqueConstraint(Lower("username"))`. Plain `unique=True` is case-sensitive,
which would let `Bob@x.com` and `bob@x.com` become two accounts  with a login
that resolves to the wrong row and a reset that mails the wrong person.

**`is_active` and `is_email_verified` are orthogonal.** New accounts are
`is_active=True, is_email_verified=False`. Marking unverified users inactive is
a common and damaging mistake: Django's password-reset flow filters on
`is_active`, so those users would be permanently unable to recover an account,
and "banned" would be indistinguishable from "has not clicked the email yet".

Note there is no `date_joined`; `created_at` serves that purpose.

### `users_profile`

Public presentation data. Primary key **is** the user FK  this enforces the
1:1 at database level, removes a surrogate key and index, and makes
`get_or_create(pk=user_id)` race-safe.

| Column | Type | Notes |
|---|---|---|
| `user_id` | bigint PK / FK → user | `on_delete=CASCADE` |
| `display_name` | varchar(60) | |
| `bio` | text(500) | |
| `avatar` | image | Randomised filename; storage resolved via a callable |
| `birthday` | date null | |
| `location` | varchar(120) | Free text, not a FK |
| `experience_level` | varchar(20) | `BakingExperienceLevel` |
| `favorite_categories` | jsonb | List of `BakingCategory` slugs |
| `created_at` / `updated_at` | timestamptz | |

### `users_preference`

Private configuration, physically separated from `Profile` so a public
serializer has no access path to privacy flags.

| Group | Columns |
|---|---|
| Privacy | `profile_visibility` (`public`/`members`/`private`), `show_birthday`, `show_location` |
| Learning | `preferred_difficulty`, `weekly_goal_minutes`, `dietary_restrictions` (jsonb) |
| Interface | `theme`, `locale` |
| Notifications | `email_course_updates`, `email_product_updates`, `email_marketing` |

Same PK-as-FK pattern.

## Tables deliberately *not* created

The Phase 0 draft of this document proposed `EmailVerification`,
`PasswordReset` and `LoginHistory`. All three are dropped:

- **Verification and reset tokens are stateless**  HMACs over user state, keyed
  by `SECRET_KEY`, that self-invalidate when that state changes. Nothing to
  store, nothing to expire, nothing to clean up. See
  [ADR 0006](adr/0006-stateless-auth-tokens.md).
- **Sessions** are owned by `django.contrib.sessions`.
- **`LoginHistory` is a real loss.** Sign-in successes and failures go to the
  `kawaiibake.security` logger with user id and IP, but there is no queryable
  forensic trail and no "active devices" screen. If either is required, that
  table has to come back  recorded honestly rather than discovered later.

## `favorite_categories`: JSON now, relation later

A `ManyToManyField("recipe_categories.RecipeCategory")` is impossible today 
that app has no models, so the field fails at system-check time, and its hidden
through table would break the three-table constraint.

Values are validated against the `BakingCategory` enum in
`apps/users/constants.py`, so the eventual backfill is an exact slug match:

1. Add the M2M alongside the JSON column.
2. Data migration: `RecipeCategory.objects.in_bulk(field_name="slug")`, copy across.
3. Drop the JSON column.

**Debt:** `BakingCategory` duplicates a taxonomy that will belong to
`recipe_categories`. Its docstring says so; move or mirror it when that app lands.

## Reserved reverse accessors

Future apps will FK **to** `users.User`. No columns are added to `User` for
them. These `related_name` values are reserved  do not reuse:

| Accessor | Owner |
|---|---|
| `recipes` | `recipes` ✓ taken (Phase 2) |
| `enrollments` | `courses` ✓ taken (Phase 3) |
| `lesson_progress` | `progress` ✓ taken (Phase 3 in lessons; moved Phase 6) |
| `course_progress` | `progress` ✓ taken (Phase 6) |
| `learning_activity` | `progress` ✓ taken (Phase 6) |
| `courses_taught` | `courses` ✓ taken (Phase 3, instructor FK) |
| `xp_transactions` | `gamification` ✓ taken (Phase 9; also `user_level`, `daily_streak`) |
| `achievements` | `certificates` ✓ taken (Phase 8) |
| `certificates` | `certificates` ✓ taken (Phase 8) |
| `gallery_posts` | `gallery` ✓ taken (Phase 11) |
| `question_threads` | `qa` ✓ taken (Phase 11; also `question_answers`) |
| `quiz_attempts` | `quizzes` ✓ taken (Phase 4) |
| `questions` | `questions` ✓ taken (Phase 4, author FK) |
| `quizzes` | `quizzes` ✓ taken (Phase 4, owner FK) |
| `reviews` | `reviews` ✓ taken (Phase 5) |
| `favorites` | `favorites` ✓ taken (Phase 5) |
| `notifications` | `notifications` ✓ taken (Phase 10; also `notification_preferences`) |
| `assistant_conversations` | `assistant` ✓ taken (Phase 7) |
| `ai_usage_logs` | `assistant` ✓ taken (Phase 7) |
| `chat_sessions` | superseded  the Phase 7 `assistant` app owns conversations |
| `reward_account` | `rewards` ✓ taken (Phase 13; transactions hang off the account) |

Also reserved on `Course`: `quizzes` ✓, `certificates` ✓ (Phase 8),
`reviews` ✓, `favorites` ✓  all taken (`lessons` is taken by the FK on
`Lesson`).

Gamification owns the `XPTransaction` ledger plus recomputed
`UserLevel`/`DailyStreak` rows (Phase 9); XP and level are **not** columns
on `Profile`, as reserved here since Phase 1.

## Phase 2  Recipes

### `recipes_recipe`

| Column | Notes |
|---|---|
| `author_id` | FK → user, `related_name="recipes"` (reserved since Phase 1) |
| `title`, `summary`, `description` | |
| `slug` | Unique, `allow_unicode=True`, CI-unique constraint |
| `difficulty` | `easy` / `medium` / `hard` / `expert` |
| `prep_minutes`, `cook_minutes` | |
| `total_minutes` | **Derived and stored** so sorting and filtering by total time use an index rather than an expression |
| `servings` | |
| `status` | `draft` / `published` / `archived` |
| `visibility` | `public` / `unlisted` / `private` |
| `published_at` | Nullable, indexed |
| `cover_image` | `ImageField(storage=get_media_storage)`  callable, so an S3 swap needs no migration |

**`status` and `visibility` are orthogonal.** Status is the editorial state,
visibility is the audience. One combined field cannot express "published but
private", and merging them would repeat the `is_active` / `is_email_verified`
mistake the users app avoids.

**`published_at` is separate from `status`** for three independent reasons: it
is the correct sort key for "newest" (a recipe drafted in January and published
in June must sort as June); it is the gate that freezes the slug; and it makes
republishing idempotent.

Indexes: `(status, visibility, -published_at)` for the listing query,
`(author, status)` for `scope=mine`, plus `total_minutes`.
Constraints: `UniqueConstraint(Lower("slug"))`, and a check that
`total_minutes <= 7 days`.

### `recipes_recipeingredient`

`recipe`, `name`, `normalized_name` (indexed), `quantity` (nullable  null means
"to taste"), `unit`, `note`, `group`, `is_optional`, `position`.

**Named `RecipeIngredient`, not `Ingredient`.** A canonical ingredient catalogue
is planned, and this document has always promised both names. Taking the shorter
name for line rows would later cost a table rename plus a coordinated frontend
rename; reserving it now is free.

`normalized_name` earns its place today  it makes "recipes containing X" an
indexed lookup and de-duplicates lines within a recipe  and it is the exact
migration key later. It is NFC-normalised: Thai combining vowels and tone marks
have several valid encodings, so de-duplication silently fails without it.

**Migration path to the catalogue** (no rows move, no endpoint changes):
create `recipes_ingredient`; group by `normalized_name` to build canonical rows;
add a nullable `ingredient_id` FK and backfill. This table then *is* the through
table  quantity and unit are properties of the line, not of the ingredient, so
they are already in the right place.

### `recipes_recipestep`, `recipes_recipeimage`

`position` is assigned by the service from the submitted array order, never
accepted from the client. There is deliberately **no unique constraint on
`position`**  it would make reordering require deferred constraints, since a
row-by-row save collides with itself immediately.

The **cover image is a column on `Recipe`**, not a flagged row here. It is read
on every list row, so a column costs zero joins, and "exactly one cover" becomes
a schema invariant rather than a constraint to trust and repair.

### `recipes_nutrition`  structure only

PK-as-FK to `Recipe`, created lazily. Ten nullable decimals (`calories_kcal`,
`protein_g`, …) where **null means unknown, not zero**, plus `basis`
(`per_serving` / `per_100g`), `source` (`manual` / `estimated` / `verified`) and
`calculated_at`.

"Structure only" means precisely: the table exists, the API round-trips it, and
**no code performs any arithmetic**  no summing over ingredients, no unit
conversion, no per-serving division. Phase 2 only ever writes `source=manual`.

`basis` and `source` ship before anything can produce an estimate for the same
reason `IssuedCredential.status` shipped before two-factor auth existed: it makes
the estimator additive later. Without `basis` every stored number would be
ambiguous and no migration could repair it.

### `recipe_categories_recipecategory`

`name`, `slug` (CI-unique), `description`, `icon`, `display_order`, `is_active`.

**No `parent`**  a self-relation on a ~20-row table is trivial to add when
hierarchy is actually needed. **No `recipe_count`**  it is one
`annotate(Count(...))` in the selector, counting only publicly visible recipes;
a stored counter would be a second source of truth able to drift.

Migration `0002` seeds this from `users.constants.BakingCategory` with identical
slugs, which is what makes the eventual `Profile.favorite_categories`
JSON → M2M backfill an exact match.

## Phase 3  Courses & lessons

### `courses_course`

Instructor FK (`courses_taught`), title/slug/summary/description, difficulty,
`status` × `visibility` (orthogonal, as recipes), `published_at`, thumbnail
(callable storage), categories M2M  plus one column that is the app boundary
made physical:

**`published_lesson_count`**  the publish gate requires "lessons exist", but
courses must never count another app's rows (that would invert the
`lessons → courses` dependency). The lessons app pushes this count through
`course_service.sync_published_lesson_count()` inside the same transaction as
every lesson mutation. It is a **rebuildable cache** (`manage.py
recount_lessons`), not a source of truth  the property that distinguishes it
from the XP-style columns this document refuses. It also serves every course
card's lesson count with zero joins.

**`published_duration_minutes`** (ADR 0021)  same pattern, same choke point,
same rebuild command: the sum of published lessons' durations, so course cards
carry a total length without a join.

**`rating_average` / `rating_count`** (ADR 0021)  stored aggregates maintained
by the **reviews** app at its own mutation choke point
(`review_repository.sync_course_rating` → `course_service.sync_rating_aggregate`,
inside the same transaction as every course-review create/edit/moderate/soft-
delete). This supersedes the earlier "ratings are computed, never stored" note
for **courses only**: the proven need is the course list carrying a rating
without an N+1, and the rebuild strategy is `manage.py
rebuild_rating_aggregates`. Per-target detail summaries (`/rating/`, with the
star distribution) remain computed on read.

### `courses_enrollment`

**One row per (user, course), forever**  unique-constrained; state changes
mutate the row. `status` ∈ active/completed/dropped; `enrolled_at` never
re-stamped; `completed_at` stamped once and never cleared (the `published_at`
pattern  the durable fact certificates will reference). Dropping is soft:
nothing is deleted, and re-enrolling restores COMPLETED if the user ever
finished.

### `lessons_lesson`

Course FK (string ref), title, content, dense server-assigned `position`
(no unique constraint  it would break bulk renumbering), `duration_minutes`,
`is_preview`, `status` ∈ draft/published (no audience of its own  the course
carries visibility), video embed fields (`video_url`/`video_provider`/
`video_duration_seconds`  external embeds only, no video infrastructure), and
a nullable `recipe` FK (`SET_NULL`)  "this lesson teaches this recipe".

Lessons are **entities with progress FKs**, so the Phase 2 collection-replace
write pattern is prohibited here: individual CRUD plus a full-array reorder
endpoint.

### Lesson progress

Owned by ``apps/progress`` since Phase 6  see the Phase 6 section below.

## Phase 4  Question bank & quizzes

### `questions_question`

Author FK (ownership only  the bank's one permitted use of the user relation
is comparing `author_id` to the viewer), `question_type` ∈ single_choice /
multiple_choice / true_false, `text`, `explanation` (post-submit learning aid),
`difficulty`, tags M2M  plus three lifecycle columns:

**`frozen_at`**  `NULL` = editable/deletable; a timestamp = content (text,
type, choices) permanently locked for historical integrity. Stamped once by
`question_service.freeze_questions()`  pushed by the quizzes app at attempt
start, the ADR 0009 counter-push mechanism carrying a timestamp. Enforced by
an optimistic conditional UPDATE (`WHERE frozen_at IS NULL`), rebuilt by
`manage.py refreeze_questions` (in quizzes  only it knows which questions
have attempts). A question knows *that* it is frozen, never *why*.

**`version` / `supersedes`** (self-FK, `SET_NULL`)  versioning preparation:
editing a frozen question will one day mean a new row pointing back at the
old, not an UPDATE. No logic uses them yet.

### `questions_answerchoice`

Question FK (CASCADE), `text`, **`is_correct`** (a per-field secret  see the
API doc), dense `position`. Frozen state is read from the parent only, so it
cannot drift. Choices of an unfrozen question are collection-replaced; frozen
choices are immutable, which is what lets attempt selections reference them
without `PROTECT` (an M2M cannot carry one).

### `questions_questiontag`

`name` (CI-unique) + unicode `slug`; created implicitly on first use.

### `quizzes_quiz`

Owner FK, title, CI-unique unicode slug (frozen after first publish),
description, `pass_percent` (0–100, check-constrained), `status` ×
`visibility` (orthogonal; `unlisted` is the lesson-integration pairing),
`published_at`. No cross-app counter  the publish gate counts
`quizzes_quizquestion`, this app's own table.

### `quizzes_quizquestion`

The composition: quiz FK (CASCADE), question FK (**PROTECT**  deleting a
bank question a quiz uses is 409), dense `position`, `points` (default 1 
the weighted-scoring seam; scoring already sums it). Unique (quiz, question).
**Nothing references these rows**, so whole-collection replace is the write
pattern  attempts snapshot what they need at start.

### `quizzes_quizattempt`

User FK, quiz FK (**PROTECT**  history blocks quiz deletion; archive is the
exit), `status` ∈ in_progress/submitted, `started_at`, `submitted_at`, and
the denormalized result block: `score`, `max_score` (stamped at **start**,
from the snapshot), `correct_count`, `incorrect_count`, `percentage`
(2 dp), `passed` (NULL until graded). Partial unique (user, quiz) WHERE
in_progress  one open attempt each, unlimited submitted history (retry
limits are a future count over these rows). Result figures are never
recomputed: history must not change when questions or quizzes change.

### `quizzes_quizattemptanswer`

The composition snapshot: attempt FK (CASCADE), question FK (**PROTECT**),
`position` and `points_possible` copied at start, `selected_choices` M2M,
`was_correct` (NULL until graded), `points_awarded`. Rows are created
**empty at attempt start**  that is what makes mid-attempt recomposition
harmless and is the prepared seam for randomized ordering and timed quizzes.
Unique (attempt, question).

## Phase 5  Reviews & favorites

### `reviews_review`

User FK plus the **explicit two-FK target** (nullable `recipe` / `course`,
CASCADE, check-constrained to exactly one  the GenericForeignKey rejection
is [ADR 0011](adr/0011-review-target-architecture.md)); `rating`
(check-constrained 1–5), `comment` (blank allowed  rating-only reviews are
legitimate), `status` ∈ active/hidden/deleted.

Nothing is hard-deleted. The duplicate rule is a **partial unique per target
on active rows only** (`(user, recipe) WHERE status='active'`), so
soft-deleting frees the slot while the row survives as history. Statistics
aggregate `ACTIVE` rows at read time via `reviews_recipe_idx` /
`reviews_course_idx`  there are no stored rating columns.

### `favorites_favorite`

Same target shape, no status: a favorite is a toggle, hard-deleted on
unfavorite. Plain uniques `(user, recipe)` and `(user, course)` suffice 
SQL ``NULL`` never equals ``NULL``, so the two target kinds cannot collide.
``created_at`` is the favorited-at timestamp future
recommendation/analytics work will consume.

## Counters deliberately not added

`favorite_count`, `rating_avg` and `review_count` are **not** on `Recipe` 
and Phase 5, which finally created the rows they would count, deliberately
did not add them: moderation makes rating aggregates volatile (a hidden
review changes the average instantly), so they are computed by
`rating_selector` in one indexed query, with the selector as the caching
seam.

A counter is not the same mistake as the XP columns Phase 1 refused: a counter
is a rebuildable cache over a ledger, with a benign failure mode. But nothing
can increment these until `favorites` and `reviews` exist, so they would be
columns permanently pinned to `0`  a lie in the database and in the API that
the frontend would build against and then have to re-handle.

They cost the same to add later, and `ORDERING_MAP` in
`apps/recipes/constants.py` is written so that swapping
`"popular": ("-published_at", …)` for `("-favorite_count", …)` is one line with
**no API change**. That is the right shape of placeholder.

## Phase 6  Learner progress

### `progress_lessonprogress`

Moved from ``lessons`` (ADR 0012) and re-shaped: completion is a **nullable
timestamp**, not a boolean-plus-timestamp pair that could drift.
``completed_at`` NULL = not completed; ``first_completed_at`` stamped once
and surviving un-completion (the ``published_at`` pattern  XP and
certificates will reference it); ``last_viewed_at`` is the resume hook a
video player will one day write. Unique (user, lesson); never deleted by
unenrollment.

### `progress_courseprogress`

Unique (user, course); **no counters**  completed/total aggregate from
``LessonProgress`` at read time, so the row can never disagree with what it
summarizes. Stores the one thing aggregation cannot recover:
``completed_at``, stamped once by conditional UPDATE when every published
lesson is complete, never cleared. Coexists with
``Enrollment.completed_at`` deliberately: enrollment is *membership* state
(courses' domain), this is *learning* state (progress' domain); the
progress app computes and tells courses through
``record_course_completion``  the Phase 3 contract with a new caller.

### `progress_learningactivity`

Append-only day-facts: unique (user, activity_date, activity_type) makes
daily recording idempotent  the entire streak substrate. Separate from
progress *state* because facts are immutable where state is not:
un-completing a lesson never erases that learning happened that day.
``quiz_completed`` / ``recipe_created`` are declared but unwired (their
producers cannot import progress without a cycle  recorded in ADR 0012).
No XP columns; future gamification reads this table.

## Phase 7  AI assistant

### `assistant_assistantconversation`

One user's chat thread. Explicit nullable targets (`recipe`/`lesson`/
`course`), never a GenericForeignKey  the reviews verdict (ADR 0011)
reaffirmed  with a check constraint allowing only the FK matching
`context_type`. Targets are **SET_NULL** (unlike reviews' CASCADE): deleting
a recipe must not delete chat history, so the constraint permits a typed
conversation with a NULL target and the service degrades it to context-free
answers. `prompt_version` is stamped at creation and never rewritten;
`language` (`th`/`en`) is per conversation, Thai default.

### `assistant_assistantmessage`

Append-only transcript: no `updated_at`, no edit/delete path anywhere.
`role` is `user`/`assistant` only  `system` is deliberately never stored
(rebuilt per send from the versioned template; the prompt-injection
boundary). Provider, model and token counts are stamped per message because
the configured provider can change mid-thread. Ordered `(created_at, id)`;
indexed by `(conversation, created_at)`.

### `assistant_prompttemplate`

Prompt text as data: unique `(name, language, version)` plus a partial
unique `(name, language) WHERE is_active`  at most one active version per
prompt. Version "1" (Thai and English, all four context types) is seeded by
data migration. Rows referenced by a conversation are never edited; new
behaviour is a new row.

### `assistant_aiusagelog`

Append-only billing/quota ledger, one row per provider call. Separate from
messages because it must survive conversation deletion (messages CASCADE
with their conversation, the ledger does not). No aggregate counter columns
anywhere; future quota reads this table live.

## Phase 8  Certificates & achievements

### `certificates_certificate`

An immutable issued record: `certificate_number` (`KB-YYYY-NNNNNN`,
globally unique, allocated by reading the year's max with savepoint retry),
`issued_at`, `verification_token` (UUID4, unique  the **only** public
lookup key; the sequential number is enumerable and never routed), and the
**printable snapshot** (`student_name`, `course_title`, `completed_at`) 
frozen at issuance per the ADR 0010 snapshot rule, which is also why
`course` can be SET_NULL without losing the record. The one mutation is
stamp-once `revoked_at`; the partial unique `(user, course) WHERE
revoked_at IS NULL` enforces one active certificate while revoked history
remains and a re-issue mints a new number. Completion is read from
`progress_selector.get_course_completed_at`  never recomputed here.

### `certificates_achievement`

Append-only earned facts: unique `(user, achievement_type)` makes awarding
idempotent (`get_or_create`); `awarded_at` and `metadata` (JSON earning
context) are never rewritten. `badge` FK is nullable + PROTECT  display
metadata, subordinate to the fact. `quiz_master`/`recipe_author` types are
declared but unwired (their sources cannot import certificates; future
awards derive via `recalculate()` reading public selectors  ADR 0014).

### `certificates_badgedefinition`

System-owned presentation, bilingual Thai-first (`title_th`/`title_en`,
descriptions, `icon`), seeded by data migration, curated only in Django
admin  no CRUD API. Deactivating hides future presentation without
un-earning anything.

## Phase 9  Gamification

### `gamification_xptransaction`

The append-only XP ledger  one row per earning event (`reason` ∈
lesson/course/quiz/certificate/review, `points`, JSON `metadata`). No
update or delete path exists; every stored aggregate is recomputed *from*
this table, so the ledger repairs the aggregates, never the reverse.
Reconciliation (`recalculate`) appends only the difference between the
owning domains' fact counts and the ledger  idempotent by monotonicity,
and never claws anything back.

### `gamification_userlevel`

One recomputed row per user (OneToOne): `current_level`, `current_xp`
(progress into the level), `total_xp` (the ledger sum). Exists solely so
the leaderboard sorts without summing ledgers; rebuilt wholesale on every
award and recalculation  no arithmetic on stored state, no history here
(history is the ledger). Indexed by `-total_xp`.

### `gamification_dailystreak`

One recomputed row per user: `current_streak`, `longest_streak`,
`last_activity_date`  all derived from progress' append-only
`LearningActivity` day-facts (the "streak substrate" of ADR 0012), never
incremented. A streak is alive while its newest day is today or
yesterday; the longest streak needs no history table because the full
calendar can always be replayed.

## Phase 10  Notifications

### `notifications_notification`

A private snapshot of one event for one recipient: `event_type`,
`title`/`body`/`actor_handle`/`link` as immutable text, stamp-once
`read_at` (nullable timestamp, the `completed_at` convention), no
`updated_at`, no delete path. **No FK to any content**  a reasoned
departure from ADR 0011: this table joins nothing, and a content FK's
only contribution would be a history-erasing CASCADE. The `link` may go
stale; that 404 belongs to the linked endpoint. Two indexes match the
two real queries: `(recipient, -created_at)` for the feed,
`(recipient, read_at)` for unread. Unread count is computed live  no
counter column.

### `notifications_notificationpreference`

One explicit choice per `(user, event_type)` (unique). **Absent row
means enabled**  nothing is seeded, defaults cost no storage, and new
event types are born enabled. A different axis from
`users_userpreference`'s email toggles: users owns the channel, this
table owns the event (ADR 0016).

## Phase 11  Community (gallery + Q&A)

### `gallery_gallerypost` / `gallery_galleryimage`

A showcase post: author, caption, two-state status
(published/unpublished  no deleted state, deletion is **hard** with
explicit media cleanup), nullable `SET_NULL` references to a recipe
and/or course  validated **publicly listed at creation** because the
post's public card joins and displays the target title. Images are a
CASCADE child with `(position, id)` ordering, positions renumbered
densely by the exact-set reorder write; the repository removes stored
files on every destructive path (Django never does). Indexes: the public
feed `(status, -created_at)`, the author wall, the image order. No
counters.

### `qa_questionthread` / `qa_questionanswer`

A question thread: author, title/body, three-state status  active
(public), hidden (moderation; author + staff still see it), deleted
(**soft**; the row and its answers survive as history but no API surface
returns them, the author included). Targets are nullable `SET_NULL` with
an at-most-one check constraint  a thread holds *other users'* answers,
so content deletion must not cascade through it. `accepted_answer` is a
nullable same-app FK: at-most-one by arithmetic (one column), replacement
is one UPDATE, and `SET_NULL` reverts the thread when the accepted answer
is hard-deleted. Answers are leaves: hard-deleted by their author,
reachable only through the thread's visibility Q
(``prefix="thread__"``). No `answer_count`  aggregates are live.

## Phase 12  Recommendation & substitution (no schema)

The one phase whose database design is the absence of tables.
Recommendations are derived results: storing them would need invalidation
machinery on every favorite, review, enrollment and publish, so the feeds
are computed per request at a flat, pinned query count instead (ADR 0018
§9). Substitution rules are an in-code registry matched through the
`normalized_name` column `recipes_recipeingredient` has carried since
Phase 2  the canonical `Ingredient` catalogue below remains future work,
and the registry's `lookup()` is the seam it will replace.

## Phase 13  Rewards

```
users_user ─1:1─▶ rewards_rewardaccount      (PK-as-FK; related_name="reward_account")
rewards_rewardaccount ─1:N─▶ rewards_rewardtransaction
                              (unique (account, event_key); CHECK amount ≠ 0)
```

**`rewards_rewardaccount`**  the one materialized aggregate of the
domain: `balance`, `lifetime_earned`, `lifetime_spent`, all
`PositiveIntegerField` (a DB CHECK under the conditional-UPDATE spend
guard, so negative balances are structurally impossible). Rebuild path
is total: all three columns recompute from the ledger
(`reconcile_rewards --apply`).

**`rewards_rewardtransaction`**  the immutable ledger, append-only in
the `XPTransaction` family: signed `amount`, `balance_after` snapshot,
`reason_code`, `event_key` (the idempotency anchor  `UNIQUE (account,
event_key)` is what makes duplicate delivery unable to grant twice),
free-text `note` and a Phase 10-style `actor_handle` snapshot for staff
adjustments. No FK to any content row  the ledger outlives everything
it rewarded (ADR 0019 §7).

## Planned entity groups (not yet implemented)

| Group | Entities |
|---|---|
| Recipes | `Ingredient` (canonical catalogue; `RecipeIngredient` becomes its through table; absorbs the Phase 12 substitution rule registry) |
| Community | `Comment` / likes / voting rows (`GalleryPost` + Q&A shipped in Phase 11) |
| Economy | shop/coupon/inventory tables  a future phase consuming the Phase 13 ledger (`RewardAccount`/`RewardTransaction` shipped; spending primitive ready) |
| Notifications | *(shipped in Phase 10)* email/digest delivery tables, if the future email phase needs any |
| AI | `EmbeddingRecord` (`ChatSession`/`ChatMessage` shipped in Phase 7 as `AssistantConversation`/`AssistantMessage`; recommendation shipped table-less in Phase 12  a `RecommendationLog` appears only if impression analytics ever justify it) |
| OAuth *(when added)* | `SocialAccount`  the one unavoidable extra auth table |

## Conventions

- Every table inherits `created_at` / `updated_at` from
  `apps.core.models.base.TimeStampedModel`.
- `BigAutoField` primary keys, except 1:1 satellites which use PK-as-FK.
- Index every FK and every field used for filtering or ordering.
- Choices come from `TextChoices` enums in each app's `constants.py`.
- JSON columns must declare `default=list` (callable)  never `default=[]`, never `null=True`.
