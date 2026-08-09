# ADR 0016 — Notifications as a Push Sink

**Status:** Accepted (Phase 10)
**Context:** Phase 10 adds `apps/notifications`: the in-app notification
center — feed, read stamps, per-event preferences — fed by exactly three
wired events. Email, push, WebSocket/SSE, digests and Celery delivery are
explicitly out of scope.

---

## 1. A push sink, where gamification is a pull consumer

The two engagement domains sit at opposite ends of the same boundary
discipline:

```
progress / certificates / quizzes / reviews
        │ facts (public selectors)              events (public service)
        ▼                                            │
   gamification  ◀── pulls, reconciles      reviews ─┤
                                            courses ─┼──▶ notifications
                                       certificates ─┘
```

Gamification (ADR 0015) consumes **derived aggregates** — "how much, in
total" — which monotonic fact counts answer perfectly at any later time,
so it pulls and reconciles. A notification is an **event in time** —
"this just happened, tell them" — and no amount of later reconciliation
can recover *when* a review arrived or deliver it promptly without
polling every domain on a timer. So producers push: an explicit,
readable call to `notification_service.notify_*()` at the site where the
event becomes true — the same mechanism as
`enrollment_service.record_course_completion` (ADR 0009 §4), pointed at
a sink instead of a peer.

The dependency arrows point **into** the sink: reviews, courses and
certificates import notifications' public service; notifications imports
no content domain at all (not even users — producers pass the actor's
public handle in). A cycle is structurally impossible.

## 2. The transaction rule: commit first, notify after

`notify()` does not insert. It registers delivery with
`transaction.on_commit()`:

- inside a producer's atomic block, delivery runs only after that block
  commits — a rolled-back review delivers nothing (tested);
- under plain autocommit (this project's default; there is no
  `ATOMIC_REQUESTS`), the callback runs immediately, after the
  producer's writes are already durable.

Either way the invariant holds: **delivery can never observe, join, or
outlive-in-reverse an uncommitted producer transaction** — achieved with
a standard library primitive, not a signal.

Delivery itself is **best-effort**: `_deliver` wraps everything —
preference check and insert — in a log-and-swallow boundary. A
notification is an announcement about a fact, not part of the fact; a
review that saved must never 500 because the announcement failed. The
producer-not-failed property is pinned by tests that make the insert
raise and assert the review persists.

## 3. Snapshot rows, deliberately without content FKs

A notification stores `title`, `body`, `actor_handle`, `link` as
immutable text — no FK to the recipe, course, review or certificate it
speaks about. This is a *reasoned departure* from ADR 0011, not a
contradiction of it: reviews and favorites need FKs because their read
paths **join** — visibility `Q` builders compose across the relation,
ratings aggregate per target. A notification is private to one
recipient and joins nothing; the only behaviour a content FK would add
is a CASCADE that erases the recipient's history when content is
deleted — precisely what rule 12 (preserve history) forbids. The `link`
is a frontend path that may go stale and 404 later; that degradation is
accepted (the assistant-context precedent, ADR 0013). The absence of
content FKs is enforced by a test that inspects the model's FK targets.

The snapshot is also the privacy boundary: its text is rendered
verbatim, so only the actor's **public handle** may enter it — never an
email, never an internal id — and tests assert emails cannot appear in
any notification payload.

## 4. Two preference axes, two owners

`users.UserPreference` (Phase 1) owns the **email channel** — broad
category toggles for a delivery medium that does not exist yet in this
app. `notifications.NotificationPreference` owns the **in-app event** —
which happenings reach the center. Different axis, different owner,
zero overlap; merging them later would put event vocabulary that only
notifications understands into the users app.

**Absent row means enabled.** Rows exist only once a user changes
something, so defaults cost no storage and no per-user seeding, and new
event types are born enabled without a migration. The preference gate
runs at delivery time, inside the best-effort boundary.

## 5. Scope held back on purpose

- **A closed event vocabulary** — Phase 10 wired three events: review
  received, course enrollment (new or reactivated; idempotent no-ops
  stay silent), achievement earned (first award only). Self-events are
  structurally absent: you cannot review your own content or enroll in
  your own course, and the achievement earner is the intended recipient.
  Adding an event type is an ADR/docs change, not just another `notify`
  call — the constants docstring says so.
  *Amended in Phase 11 (ADR 0017):* two Q&A events joined the
  vocabulary — `qa_answer_received` and `qa_answer_accepted` — with
  self-event guards in the producer (`answer.author != thread.author`)
  and the same post-commit best-effort delivery.
- **No unread counter column** — `COUNT(*) WHERE read_at IS NULL` on an
  indexed pair, always true (rule 14).
- **No repository** — the writes are a single create and two
  conditional UPDATEs; a repository layer would be ceremony (rule 15).
- **Email / push / realtime / digest deferred.** The async seam is
  `_deliver`: today it inserts synchronously; a future phase makes it
  enqueue a Celery task (the stub `tasks/` convention) or fan out per
  channel, without touching `notify()`'s contract or any producer.
  Read-side realtime (SSE/WebSocket) would sit behind the selector the
  same way.

## Consequences

- A notification's text can disagree with renamed content — it says
  what was true when it happened, like a certificate says what was true
  when printed.
- `mark_all_read` is one conditional bulk UPDATE bounded by the
  recipient + unread index; fine at present scale, revisit if feeds
  reach millions of rows per user.
- Reactivated enrollments notify again by design — a returning student
  is news; an active student double-clicking enroll is not.
- The producer wiring adds one lazy `enrollment.user.username` fetch on
  new enrollments (one row, once per enrollment event) — accepted over
  widening repository signatures.
