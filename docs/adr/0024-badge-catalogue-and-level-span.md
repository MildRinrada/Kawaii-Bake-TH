# ADR 0024  The badge catalogue is readable; the level curve is stated

- **Status:** Accepted
- **Date:** 2026-08-09
- **Supersedes:** nothing
- **Superseded by:** nothing

## Context

The achievements screen has to show two things the API could not answer:

**1. What is there to earn?** `BadgeDefinition` is system-owned display
metadata  seeded by migration, curated in Django admin, with
"deliberately **no CRUD API**" per its own docstring. That rule is about
*writes*, but the absence of any read meant the definitions were only
reachable through an achievement a user had already earned. A client
could therefore render earned badges and nothing else: no catalogue, no
"3 of 5 unlocked", no locked cards, no unlock conditions. The only way
to draw them would be to hardcode the badge list in the frontend  a
second, silently-drifting copy of seeded backend data.

**2. How far through the current level is the learner?**
`/me/gamification/` returned `current_level`, `current_xp` and
`total_xp`, but not the span of the current level. `current_xp` is XP
*into* the level, so a progress bar needs the denominator. It exists 
`level_service.LEVEL_STEP`, as `level * 100`  but only server-side. A
client drawing the bar would have to restate the curve, which is
business logic living in exactly one place by design.

## Decision

Two additive, read-only changes.

**`GET /api/v1/achievements/`**  the active badge catalogue.
Unpaginated (a small curated set), `AllowAny`, and user-independent by
construction: it answers *which achievements exist*, never *who has
them*. Inactive badges are excluded, so deactivating one hides it from
the catalogue without un-earning anybody's achievement  the existing
purpose of `is_active`.

The route deliberately sits beside, not inside, the owner-scoped one:

| Route | Answers | Scope |
|---|---|---|
| `GET /api/v1/achievements/` | what there is to earn | public, system-owned |
| `GET /api/v1/me/achievements/` | what I have earned | owner-only, append-only facts |

**`xp_for_next_level`** on the `/me/gamification/` level payload, sourced
from a new public `level_service.xp_for_level()` that `calculate_level`
now also uses  one statement of the curve, consumed by both.

## Consequences

**Positive**

- The achievements page can show locked badges with their real unlock
  conditions, and a true "earned / total" figure, without the frontend
  owning a copy of the badge list.
- The level bar renders from a server-stated denominator; the curve can
  change in `level_service` without a frontend release.
- The fact/definition separation is now expressed in the URL structure
  rather than implied.

**Negative / accepted**

- The catalogue reveals which achievements exist to anonymous visitors.
  That is marketing copy, not user data  the same category of
  information as the recipe-category list, which is already public.
- Two badge types (`quiz_master`, `recipe_author`) are declared and
  seeded but not yet awarded by any code path. They will now appear as
  permanently locked until a future phase wires them. Their unlock text
  is accurate; what is missing is the awarding rule, not the badge.

**Rejected alternatives**

- *Hardcode the badge list in the frontend.* Duplicates seeded backend
  data with no mechanism to keep the copies in step, and `is_active`
  would stop working.
- *Return locked badges from `/me/achievements/` with an `earned` flag.*
  Collapses the fact/definition split this app was built around, and
  makes an append-only ledger endpoint responsible for presenting things
  that never happened.
- *Compute `level * 100` in the frontend.* Moves business logic into the
  presentation layer, which is the thing the project's layering exists
  to prevent.

## Known gap this ADR does not close

No endpoint reports **progress toward a locked achievement** (for
example "2 of 3 sourdough lessons"). The awarding services evaluate
their conditions at award time and store nothing partial. The
achievements page therefore shows each locked badge's *condition* and no
progress bar  an invented percentage would be worse than none.
