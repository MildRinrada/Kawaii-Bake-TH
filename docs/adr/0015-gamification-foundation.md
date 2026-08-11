# ADR 0015  Gamification Foundation

**Status:** Accepted (Phase 9)
**Context:** Phase 9 adds `apps/gamification`: the XP ledger, derived
levels, daily streaks and the public leaderboard. Rewards, coupons,
inventory, missions and seasonal events are explicitly out of scope for
this phase.

---

## 1. Why gamification is a pure consumer

Gamification owns three tables  the XP ledger and two derived rows  and
**zero facts**. Everything it says about a user is computed from facts
other domains own, read through their public selectors:

```
gamification ──▶ progress      (completed lessons/courses, activity days)
             ──▶ certificates  (distinct certified courses)
             ──▶ quizzes       (distinct submitted quizzes)
             ──▶ reviews       (active review count)
```

No domain imports gamification, nothing is pushed in, and the flow the
spec mandates  *LearningActivity → gamification reads → award XP*  is
the only flow that exists. This is the Phase 8 "pure consumer of stamped
facts" precedent taken to its limit: if this app were deleted, every
other domain would be untouched; if its tables were dropped, one
recalculation per user rebuilds them. That reversibility is the design
goal  game mechanics are the most churn-prone part of any product, and
they must be re-tunable (or removable) without touching learning data.

The spec's dependency sketch names progress, certificates and quizzes;
`review_written` XP (mandated by the XP rules) requires one more read, so
reviews joined the consumer list via the same additive-public-selector
mechanism as the other three. The hard rule  no domain imports
gamification  is unaffected.

## 2. Why XP is append-only

`XPTransaction` is history: no edit, no delete, no update path in the
repository  the append-only family (LearningActivity, AssistantMessage,
AIUsageLog, Achievement). An editable ledger cannot be an audit trail,
and the future reward economy (spending XP, seasonal boosts) will need
exactly this property: a balance you can *prove* by replaying history.
Reconciliation is additive by construction: the derived fact counts are
monotonic (append-only sources, stamp-once timestamps, distinct-entity
counts), so `recalculate()` only ever appends the difference between
facts and ledger  running it twice appends nothing, and it never needs
to (and never may) remove an entry. XP values live in `xp_service.XP_RULES`
 rules are code, not rows: changing a value plus recalculation re-derives
consistently, with the ledger keeping what was actually awarded at the time.

## 3. Why levels are derived

`UserLevel` is a **recomputed aggregate**, not a source of truth: every
field is a function of the ledger sum (`level_service.calculate_level`,
a progressive curve  level *L* → *L+1* costs *L* × 100 XP). The row
exists for one reason: the leaderboard must sort by XP without summing
ledgers per request. It is the counter-push lesson (ADR 0009) applied
internally  a stored aggregate is fine *when its rebuild path is total*:
`_refresh_level` overwrites the whole row from the ledger on every award
and every recalculation; no arithmetic is ever performed on stored state.
No level history is kept  history is the ledger, and any past standing
can be replayed from it.

## 4. Why streaks derive from LearningActivity

ADR 0012 built `LearningActivity` as "the streak substrate": append-only
day-facts, unique per (user, date, type), surviving un-completion. The
streak service consumes exactly that  the full distinct-date history 
and recomputes `current`, `longest` and `last_activity_date` from
scratch every time. **Never incremented**: an increment ("+1 if you did
something today") is a distributed counter smeared across days, wrong the
first time a job double-fires or misses a day, and unable to backfill.
Derivation from the immutable calendar cannot drift and repairs itself by
existing. A streak is alive if its newest day is today *or yesterday* 
studying at 23:59 must not require studying again by 00:00 to keep the
flame.

## 5. Why the leaderboard exposes the public handle only

A leaderboard row is `public_handle`, `level`, `total_xp`  nothing
else. The endpoint is anonymous (a leaderboard is *for* being seen), so
its payload is the platform's most-scraped surface: no email, no user id,
no name, no avatar URL  the handle is the identity users chose to be
public (Phase 1 separated it from the email login for exactly this kind
of surface). Only users with a derived level row appear; opting out (a
privacy preference) can later filter this queryset without touching the
ledger.

## 6. Why rewards are postponed

Rewards turn XP from a scoreboard into a **currency**, and currency
brings an economy: spend transactions (the ledger gains negative
entries and a no-overdraft invariant), inventory, coupon redemption
against real-world value, fraud pressure on every earning path, and
balance-vs-replay consistency questions. None of that changes the
foundation laid here  earning stays append-only, standing stays derived
 but all of it deserves its own phase and ADR rather than riding along.
The foundation is deliberately reward-ready: an auditable ledger, rules
in one service, and idempotent reconciliation are precisely the
prerequisites an economy audits against.

## 7. Why gamification never uses signals

The scaffold's `signals/` directory was deleted, not filled. Signals
would invert the dependency silently: `progress` firing a signal that
gamification receives is `progress → gamification` coupling wearing a
disguise  the owner's transaction now runs a consumer's code, failures
in XP awarding would break lesson completion, and the coupling is
invisible to anyone reading either app. The standing no-signals rule
(ADR 0009 §4) has held through seven cross-app phases of explicit calls
in the allowed direction; this phase needed not even that  pull-based
reconciliation means the producing domains do nothing at all. The
trade-off is accepted openly: XP is eventually consistent, current as of
the last recalculation (user-triggered now; a scheduled Celery sweep
later changes cadence, not architecture).

## Consequences

- XP updates when `recalculate` runs  the summary can lag new facts
  until the user (or a future scheduled job) triggers it. Accepted:
  honesty about derivation beats a hidden push edge.
- Per-event metadata is thin for reconciled entries (`source:
  recalculate` rather than "which lesson"); the facts themselves remain
  queryable in their owning domains.
- `quiz_completed` XP counts distinct submitted quizzes, not attempts 
  unlimited retries must not be an XP farm.
- Deleting a review (or a moderator hiding it) lowers the *derived*
  count but never claws back awarded XP  the ledger is append-only and
  reconciliation only tops up. Earned is earned.
