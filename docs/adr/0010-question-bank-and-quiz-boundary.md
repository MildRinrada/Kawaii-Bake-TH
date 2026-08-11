# 0010  The question bank and the quiz ↔ question boundary

**Status:** Accepted (Phase 4)

## Context

Phase 4 adds assessments: a reusable **question bank** (`questions`) and
**quizzes** with attempts and scoring (`quizzes`). Two properties dominate the
design: questions must be *reusable* (one question, many quizzes, never
duplicated), and attempt history must be *permanent* (a recorded score must
still mean tomorrow what it meant today, whatever instructors edit later).

## Decision 1  `questions` is a leaf; `quizzes` depends on it

```
lessons ──▶ quizzes ──▶ questions
```

The composer depends on the asset, never the reverse. `questions` imports no
feature app and knows nothing about quizzes, attempts, scores or XP  that
ignorance is what makes the bank reusable by any future consumer (lesson
inline checks, AI-generated practice). All communication is calls into the
questions app's public selectors and services; `QuizQuestion.question` and the
attempt FKs are lazy string references (ADR 0008).

**The one nuance:** `Question.author` is a user FK. The permission matrix
("owners manage their own bank") requires ownership, and the recorded rule is
that the bank's entire knowledge of users is the `author_id == viewer_id`
comparison  no join into profiles, preferences or enrollments, ever.

**Known constraint:** deleting a user cascades to their questions, which
`PROTECT` blocks if any quiz or attempt references them. Phase 1 deactivates
rather than deletes accounts, so this is recorded, not solved.

## Decision 2  Question freezing (`frozen_at`)

A question that has been answered in an attempt can no longer have its
content edited or be deleted. The state lives on `Question.frozen_at`:

* **Questions owns the state, quizzes owns the reason.** A question knows
  *that* it is frozen, never *why*. The quizzes app  the one that knows
  attempts are about to reference the question  pushes the state through
  `question_service.freeze_questions(ids)`. This is ADR 0009's counter-push
  mechanism carrying a timestamp instead of a number. (The rejected
  alternative, a `has_attempts` flag, leaked another domain's vocabulary into
  this schema; deriving the state via `Exists()` on quiz tables would invert
  the dependency outright; signals are banned by policy.)
* **A timestamp, not a boolean**  stamped once, never cleared; the same
  pattern as `published_at`/`completed_at`, and the audit trail is free.
* **Freeze happens at attempt start, not submit.** The snapshot's promise is
  "graded against what was asked"; freezing at submit would leave a window
  (start → submit) in which the key could change under the taker. Freeze and
  snapshot creation commit or roll back in one transaction.
* **`freeze_questions` is idempotent.** Already-frozen is the desired end
  state, not a conflict  every second student starting the same quiz meets
  questions the first student froze. The only error is an unknown id.
* **Enforcement is optimistic, no `select_for_update`.** Every content
  mutation's first statement is the *gate write*:
  `UPDATE … SET updated_at = now WHERE id = ? AND frozen_at IS NULL`.
  Zero rows affected means frozen (409 `question_frozen`) or gone (404); one
  row means the mutation now holds the row's write lock, so a concurrent
  freeze serializes against it with no declared locking and no race window.
* **What freezes:** `text`, `question_type`, and the choice set.
  `explanation` (a post-submit learning aid), `difficulty` and `tags` stay
  editable  organising the bank is not rewriting history.
* **Rebuild lives in quizzes:** `manage.py refreeze_questions` finds every
  question referenced by attempt history and re-pushes the freeze through the
  public API. Only quizzes can know the list; questions owns the column.
  Strictly monotonic  an abandoned attempt may leave an over-freeze, and
  over-freezing is the safe direction.
* **Escape hatch:** duplicate the question today; versioning tomorrow. The
  `version` and `supersedes` fields prepare it: editing a frozen question
  becomes a *new row* (version+1, `supersedes` pointing back) that quizzes
  upgrade to explicitly, while old attempts keep pointing at what was asked.

## Decision 3  Attempt snapshots must be complete

`POST /quizzes/{slug}/start/` creates, in one transaction: the freeze (above),
the `QuizAttempt` (with `max_score` stamped **now**), and one empty
`QuizAttemptAnswer` row per composition entry with `position` and
`points_possible` copied from `QuizQuestion`.

The principle: **after start, grading may read nothing mutable.** Grading
consumes only the snapshot rows and the frozen bank's answer keys  never the
live composition. That makes whole-composition replacement (`question_ids` on
PATCH) safe at any time, including mid-attempt, and it is why `QuizQuestion`
may use the Phase 2 collection-replace pattern that lessons had to ban:
nothing references composition rows. Creating answer rows at start is also
the prepared seam for randomized ordering and timed quizzes.

All result figures (score, counts, percentage, passed) are denormalized onto
the attempt at grading time and never recomputed  deliberate, so history
survives later edits. The one-shot conditional transition
(`WHERE status = 'in_progress'`) guarantees an attempt is graded exactly once;
submit is deliberately **not** idempotent (409), unlike enroll, because a
second submit may carry different answers.

## Decision 4  Scoring strategy

Pure functions in `scoring_service`, one grader per question type in a
registry: single choice and true/false are *exact-one*, multiple choice is
*exact-set* (no partial credit this phase). A skipped question grades as
incorrect. `points` on `QuizQuestion` (default 1) flows through
`points_possible` into the engine, so weighted scoring is a future authoring
change, not an engine change; negative scoring would be one more grader
concern. Future types plug in as one grader + one validator with no schema
change  choice-less types simply have no `AnswerChoice` rows.

## Decision 5  The answer key is a structural secret

`is_correct` never travels in any taker-facing payload. The taker read path
is DTOs that **lack the field** (`TakerQuestionDTO`), the key lives in its own
screaming-name module (`selectors/answer_key.py`) whose sole legitimate
caller is scoring, choices are ordered by `position, id` only (a correct-first
sort would leak through row order), and a sweep test asserts the string
`is_correct` is absent from every taker response. The only surface that
renders correctness is the owner's own bank endpoint. After submit, takers see
`was_correct` and `explanation`  the outcome, never the key.

## Decision 6  Visibility instead of COURSE_ONLY

Quizzes get the standard status × visibility axes (public / unlisted /
private), not a course-gated mode. True `COURSE_ONLY` would require quizzes to
know which lessons link them and who is enrolled  the forbidden direction.
`unlisted` covers the integration case: a quiz linked from an
enrollment-gated lesson never appears in browse and is only reached through
the lesson. Archived quizzes stay readable to anyone with attempt history
(the archived-but-enrolled precedent), while new attempts require
`published`. Lesson-context attempts remain future work if a hard gate is
ever needed; it would be lessons *reading* `attempt_selector` (allowed), not
quizzes writing toward lessons.

## Consequences

* A typo in an attempted question is permanent until versioning ships;
  duplicate-and-relink is the documented workaround.
* Published quizzes are takeable by any authenticated user who can see them 
  the quiz is the measuring tool, not the paywall; lesson content remains the
  gated asset.
* Admin edits bypass the service-layer gate (operator override);
  `refreeze_questions` repairs freeze drift, and attempt rows are immutable
  in admin.
* `QuizAttemptAnswer.selected_choices` cannot be `PROTECT` (M2M), but the
  invariant holds structurally: selections only ever reference choices of
  frozen questions, whose choice rows cannot be deleted.
