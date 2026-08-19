# ADR 0033 - What a question board has to tell you before you click

- **Status:** accepted
- **Date:** 2026-08-11
- **Phase:** Q&A board completion

## Context

`/threads` listed every question with its title, its asker, and the
recipe it was about - and nothing else. Sorted by creation date, only.
That is enough to render a list and not enough to choose from one: the
reader cannot see whether a question has been answered twice or not at
all, whether anyone has looked at it, or whether the "3 days ago" thread
was answered an hour ago. An empty thread titled "test" sat at the top of
the board permanently, because newest-first is the only order there was.

## Decisions

### 1. Three numbers, all aggregated at read time

`answer_count`, `view_count` and `last_answer_at` are annotations on the
thread queryset - `Count("answers", distinct=True)`,
`Count("views", distinct=True)`, `Max("answers__created_at")`. The
`QuestionThread` docstring already promised "No `answer_count` - it
aggregates live"; this keeps that promise for all three. Both counts pass
`distinct=True` because the two aggregates share one query and would
otherwise multiply each other.

Every read goes through `qa_selector`, so the fields are always present -
including the ones returned by create/patch/accept, which reload through
the same selector.

### 2. A view is a row, and only for signed-in readers

`ThreadView(thread, user)` with a unique constraint, recorded in the
thread-detail `GET` and idempotent by `IntegrityError` (the enrollment
and gallery-like precedent). Refreshing cannot inflate it, so the number
means *readers*, not *requests*.

Anonymous readers are deliberately not counted. Counting them means
minting a session cookie for every passer-by - a bigger promise to make
in a cookie policy than a view tally is worth - and session-keyed rows
grow without bound. The UI says "คนอ่าน" against signed-in readers and
does not pretend to be a traffic metric.

The response carries the count from *before* the current read: showing
someone a number they just incremented reads as a bug.

### 3. Sorting is a preference, so bad input is not an error

`ordering` accepts `latest` (default), `active` (most recently answered)
and `popular` (most readers); anything else silently falls back to
`latest` rather than returning 400. Every ordering ends in
`-created_at, -id` so pagination cannot repeat or skip a row, and
`active` uses `F("last_answer_at").desc(nulls_last=True)` explicitly -
SQLite and PostgreSQL disagree about where NULL sorts, and an unanswered
thread must land at the bottom on both.

### 4. Filters compose, and only narrow

`resolved` (has an accepted answer), `target` (recipe/course) and
`category` (the target's category slug - one filter spans both kinds
through an OR) join the existing `recipe_id`, `course_id` and `search`.
Nothing here widens a result set; the visibility `Q` is applied first and
is never optional.

### 5. "Needs an answer" is derived, not stored

A thread that is old and has no answers is computed by the client from
`created_at` + `answer_count`, against `NEEDS_HELP_AFTER_HOURS`. There is
no flag column and no job to set one: a fact that can be derived from two
fields the payload already carries should not become state that can go
stale.

## Consequences

- `GET /qa/threads/` gains `resolved`, `target`, `category` and
  `ordering`; every thread payload gains three fields.
- Opening a thread now writes one row the first time each reader does so.
- The board can offer "still waiting for an answer" as a real filter,
  which is what turns a list into something a helper can work through.
- A future public view count (including anonymous traffic) would need a
  different mechanism and a cookie-policy change; this ADR does not
  create a path to it by accident.
