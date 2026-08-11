# ADR 0019  Rewards Economy

**Status:** Accepted (Phase 13)
**Context:** Phase 13 adds `apps/rewards`: a reward account with a
materialized balance, an immutable ledger, pull-based earning from
identified learning facts, service-level spending, and audited staff
adjustments. Shops, redeemables, coupons and seasonal events are
explicitly out of scope.

---

## 1. Rewards owns the ledger; source domains stay fact owners

The invariant of the phase: *progress owns "completed", quizzes owns
"submitted", certificates owns "certified" and "achieved"  rewards owns
only the economic consequence.* Every earning is derived by reading the
owning domain's **public identified-fact selector** (the Phase 9
additive-selector door: `completed_lesson_ids`, `completed_course_ids`,
`completed_quiz_ids`, `certified_course_ids`, `earned_types`). Rewards
never re-derives a definition  "course completed" is whatever progress
stamped, "distinct submitted quiz" is the quizzes anti-farming rule,
"distinct certified course" is the certificates revoke-reissue rule.
No producer imports rewards; deleting the app touches nothing else.

## 2. The event boundary is the existing pull mechanism, upgraded

The project already has two event boundaries: the gamification **pull**
(ADR 0015  reconcile a derived ledger up to fact counts) and the
notifications **push** (ADR 0016  for event-time UX that cannot be
reconstructed). Reward facts are fully reconstructible, so rewards
reuses the pull boundary  no second event architecture, no generic
event table. The one upgrade: XP reconciles **counts**, a currency must
reconcile **identities**. `claim` maps each source fact to a stable
``event_key`` (`lesson_completed:42`), because §3 below needs per-event
idempotency that count arithmetic cannot give.

## 3. Idempotency is a database constraint, not a check

The same event will be delivered twice  HTTP retries, double-clicked
claims, a future async worker. `UNIQUE (account, event_key)` is the
guarantee: two racers both pass any `if exists` check, but only one
insert commits; the loser's savepoint rolls back its balance update too
and the existing row is returned. Duplicate delivery is therefore
*behaviourally idempotent*  same response, zero economic effect.
Spends and staff adjustments get the same protection through
caller-supplied idempotency keys.

## 4. Why the balance is materialized

The one stored aggregate in the domain, with the read reason
Database.md demands: the summary endpoint, every spend guard and every
future shop lookup would otherwise scan the ledger. The rebuild path is
total  `balance = Σ amounts`, `lifetime_earned = Σ positive`,
`lifetime_spent = Σ |negative|`  and `reconcile_rewards --apply`
recomputes all three from the ledger, so drift is repairable evidence,
never permanent corruption.

## 5. Concurrency protection is the database's job

Python-level locks protect one process; the deployment target is many.
Two mechanisms carry all correctness:

- **Debits** are a conditional UPDATE  ``WHERE balance >= amount`` 
  so check-and-debit is one statement and zero rows updated *is* the
  insufficient-funds answer. The row lock the UPDATE takes holds to
  commit, serialising rivals. `PositiveIntegerField`'s CHECK is the
  second net: a negative balance is structurally impossible.
- **Duplicates** die on the unique event key (§3).

Everything runs inside one `transaction.atomic()` block: no ledger row
without its balance move, no balance move without its ledger row.

## 6. Why transactions are immutable

The ledger is the audit trail  the `XPTransaction`/`LearningActivity`
append-only family. No service, repository or API updates or deletes a
row; each row snapshots what/why/how much/`balance_after`/which
event/when, so history stays answerable even if rules change later.
Corrections are new adjustment entries (§9), never edits.

## 7. No GenericForeignKey, no signals

A GFK from transactions to source objects would join nothing usable,
break referential integrity, and couple the ledger's lifetime to
content rows that legitimately get deleted (ADR 0011's reasoning, ADR
0016's snapshot conclusion). The `event_key` string carries exactly the
identity needed for idempotency and audit, nothing more. Signals remain
banned (standing rule): the pull design needs no producer-side hook at
all, which is the strongest form of decoupling.

## 8. Achievements, certificates, progress stay separate domains

Rewards did not absorb them and does not mirror their tables. Each
remains the sole authority on its facts; rewards holds only derived
economic rows keyed to those facts. A rule change (say, quiz points
5→10) is a rewards-only edit; a fact-definition change (what counts as
"completed") stays a producer-only edit  the boundary keeps both
diffs small and separately reviewable.

## 9. Staff adjustments are ledger entries

Staff never touch the balance column. An adjustment flows through the
same service and the same atomic write path as everything else, with a
**required reason** and the actor's public handle snapshotted
(Phase 10 style  text, no FK, so the audit survives staff-account
churn). Downward adjustments obey the same `balance >= amount` guard:
not even staff can overdraw an account. Permissioning is DRF's existing
`IsAdminUser`  no new permission system.

## 10. Reconciliation is monotonic

`reconcile_rewards` (dry-run by default, `--apply` to write) repairs in
exactly two directions, both safe: it **appends** earnings whose
authoritative source fact exists but whose ledger entry is missing (the
same computation as `claim`), and it **recomputes** the materialized
account aggregates from the ledger  this app's own derived state. It
never deletes a transaction, never subtracts a suspected overpayment,
never invents a fact. Historical facts that carry no identity (none
currently  every wired source has one) would be reported, not guessed.

## 11. Spending without a shop

The spend primitive exists so a later shop phase consumes it instead of
inventing its own balance mutation  the debit guard, the idempotency
key, the ledger row are all settled now. Deliberately, there is **no
user-facing spend endpoint**: there is nothing to buy, and an endpoint
that burns points for nothing is an attractive nuisance. The service
seam (`reward_service.spend`) is the extension point.

## 12. Thai is first-class

A reason is a stable machine code plus authored Thai and English titles
(`REASON_TEXT`), serialized as `{code, title_th, title_en}`  the badge
precedent (ADR 0014), not a translation fallback. A registry test
rejects any reason whose Thai title contains no Thai characters, so
English-as-Thai cannot ship. Free-text fields (spend notes, adjustment
reasons) round-trip Thai through the full path, proven over live HTTP.

## 13. Future extension points

- **Shop/redeemables/coupons/inventory**: consume `spend` with
  idempotency keys; item tables arrive with that phase, not before.
- **`recipe_created` rewards**: deliberately unwired  publishing has
  no quality gate, so it is a spam mint until moderation exists.
- **Streak multipliers / seasonal events**: a rule-layer concern 
  `REWARD_RULES` becomes a function of context in that phase.
- **Async delivery**: a worker calling `claim` per user is already safe
   idempotency was designed for it.
- **XP/levels/leaderboard**: remain gamification's (Phase 9); the two
  ledgers stay separate currencies with separate semantics on purpose 
  XP is reputation (never spent), rewards are money (spendable).
