# ADR 0017 — Community Content: Gallery + Q&A

**Status:** Accepted (Phase 11)
**Context:** Phase 11 adds the community layer: `apps/gallery` (showcase
posts with images) and `apps/qa` (question threads with answers). No
follows, feeds, hashtags, voting, reputation, AI answers, likes/comments
or moderation dashboard — those are future phases with boundaries noted
below.

---

## 1. Two apps, not one "community" app

Gallery and Q&A share a *category* (user-generated content about content)
but nothing structural: different lifecycles (hard-delete media vs
soft-delete discussion), different invariants (image ordering vs accepted
answer), different privacy shapes. One app would be a junk drawer bound
by a word. Two small domains follow the one-domain-one-app rule that has
held since Phase 1.

## 2. Dependency direction

```
recipes ──▶ gallery        recipes ──▶ qa
courses ──▶ gallery        courses ──▶ qa          (references, read via
                                                    public selectors/refs)
gallery ──▶ notifications? — no: gallery wires no event this phase
qa      ──▶ notifications  (push sink, ADR 0016 mechanism)
```

Content apps know nothing of either community app; there is no FK from
Recipe/Course toward them, and notifications never imports back. Gallery
interactions (likes/comments) were **not** implemented, so gallery has no
notification event yet — wiring one without an interaction would notify
no meaningful happening.

## 3. Content reference strategy

Both apps reference content with **nullable `SET_NULL` FKs**, not
reviews' CASCADE and not a GFK:

- *Not CASCADE*: a thread contains other users' answers and a post
  contains the author's photos; deleting a recipe must not silently
  destroy either (rules 10/12). `SET_NULL` degrades to "context gone",
  the assistant precedent (ADR 0013).
- *Not GFK*: the ADR 0011 arguments hold verbatim — real integrity,
  typed OpenAPI, joinable filter columns (`?recipe_id=`, category
  filtering through `recipe__categories`).
- *Gallery-only rule*: the reference must be **publicly listed at
  creation** (checked through the content apps' public listing
  selectors). A gallery post is public; its card joins and displays the
  target's title, so referencing private/unlisted content would leak it.
  Residual staleness — content hidden *after* posting still shows its
  title on old cards — is accepted and recorded, same as notification
  snapshots. Q&A validates through the asker's own ref visibility
  (reviews rule) since a thread names its target in prose anyway.

## 4. One visibility Q per domain

`gallery_visibility.visible_q` (published ∪ own ∪ staff) and
`qa_visibility.visible_q` (active ∪ own-hidden ∪ staff-hidden; deleted
never) are each the **only** implementation of their rule — list, detail,
search, filters and (for Q&A) the answers endpoints all compose the same
builder; answers reach it through `prefix="thread__"`, the Phase 3
mechanism. There is deliberately no `can_view_thread()` twin.

## 5. Image lifecycle

Single-image multipart endpoints (the recipes pattern — nested file
arrays in multipart are impractical), byte-level validation **before**
storage is touched (a rejected upload writes no file), append-at-end
positions with `(position, id)` ordering, and reorder via a `PATCH`
`image_ids` exact-set array (the lessons reorder invariant — no separate
endpoint). Deletion is the repository's job: files are collected before
the row cascade and removed after the commit, so a failed transaction
deletes no media and a committed one leaves no orphans — proven by tests
and by the live e2e checking the disk.

## 6. The accepted-answer invariant

`QuestionThread.accepted_answer` is a nullable same-app FK. "At most one"
is enforced by arithmetic, not constraint: one column cannot point at two
rows, so replacement is a single-field UPDATE whose unset-the-old is
implicit and atomic. `SET_NULL` on the pointer means deleting the
accepted answer reverts the thread to unanswered at the database layer —
no application code to forget. Only the thread author (or staff) accepts;
the answer must belong to the thread; re-accepting the same answer is
idempotent and does not re-notify.

## 7. Delete / history policy — chosen by semantics, not by reflex

- **Gallery: hard delete + media cleanup.** A post is one author's own
  artifact; nothing historical references it, keeping dead bytes would be
  pure liability, and users deleting photos of their kitchen expect the
  photos *gone*.
- **Q&A threads: soft delete** (`status=deleted`). A thread is a shared
  artifact — the answers are other users' labor. The row and answers
  survive in the database, but *no* API surface returns them, the author
  included: deleted means unreachable, not "archived for the owner".
- **Q&A answers: hard delete.** An answer is a leaf owned by one author;
  the only inbound pointer (`accepted_answer`) heals itself via
  `SET_NULL`.

## 8. No counters

No `answer_count`, `image_count`, `like_count`. Every displayed number is
a live aggregate or the pagination `count`; the only stored orderings are
`position` columns with a total rebuild path (the reorder write). The
standing rule: an aggregate column requires a proven query need and a
rebuild strategy; none exists here.

## 9. Identity in payloads

Every public payload names users by `public_handle` (`author_handle`)
only — the Phase 1 email/handle split doing its job on the two most
scrapable new surfaces. Privacy tests assert emails cannot appear in
gallery or Q&A payloads.

## 10. Notification integration

Two new vocabulary entries (ADR 0016 amended): `qa_answer_received`
(someone answered your question) and `qa_answer_accepted` (your answer
was chosen). Both flow through the Phase 10 sink unchanged — post-commit
via `on_commit`, best-effort, preference-gated, self-events skipped in
the producer (`answer.author != thread.author` guards both). No new
notification tables or services; qa imports only the public
`notification_service`.

## 11. No signals

Both scaffolds' `signals/` directories were deleted. Producer-side
explicit calls (qa → notifications) and database-level referential
actions (`SET_NULL`) cover every cross-object reaction this phase needs.

## 12–13. Future boundaries

- **Moderation**: staff hide/restore exists at the field level
  (`status`, reviews-style, 403 for non-staff). A moderation *dashboard*,
  audit log, and reason codes are a future phase — they must build on
  these statuses, not replace them.
- **Likes/comments/voting/reputation**: interactions will be their own
  rows (per-user facts, unique-constrained, aggregated live — the
  favorites/XP patterns), never counter columns on posts/answers. A
  gallery interaction event joins the notification vocabulary when it
  exists.

## 14. `apps/qa` vs `apps/questions`

They share an English word and nothing else. `questions` is the
assessment item bank: authored, versioned, frozen-for-history, with
structurally secret answer keys (ADR 0010). `qa` is open conversation:
public, editable, moderated, with a socially "accepted" (not *correct*)
answer. Merging them would put answer-key secrecy machinery and public
discussion in one privacy domain — the exact kind of boundary collapse
the app-per-domain rule exists to prevent. The label `qa` keeps the URL
(`/api/v1/qa/…`) and reverse accessors (`question_threads`,
`question_answers`) unambiguous beside `/api/v1/questions/`.

## Consequences

- A gallery card can name a title its content owner later hid (accepted,
  §3). A `link`-style staleness, not a leak of anything unnamed at
  posting time.
- Thread search is `icontains` over title/body — adequate for community
  volume; the recipes search-backend seam is the upgrade path if it ever
  isn't.
- Soft-deleted threads accumulate; an operator purge command can be
  added later without API change.
- Gallery has no notification event until interactions exist — an
  unpublished post silently disappearing from the feed needs no
  announcement.
