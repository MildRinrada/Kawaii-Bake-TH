# ADR 0020  Profile UX & Personalization Backend

**Status:** Accepted (Phase 14)
**Context:** Phase 14 completes the Phase 1 profile/preferences layer as
the platform's explicit-personalization source: the promised
favourite-category backfill to the real taxonomy, an assistant-compatible
Thai-first language preference, derived profile completion, and a
read-only `/me/settings/` composition. No second profile system, no new
tables  one migration on existing tables.

---

## 1. Users owns explicit personalization; nothing else moved

Three concepts stay physically separate: **identity** (`User`  email,
handle, account state), **explicit preferences** (`Profile` +
`UserPreference`  what the user *tells* the system), and **derived
behavior** (favorites, reviews, enrollments, completions  owned by
their source domains, forever). Phase 14 changed only the middle one.
No behavioral history was copied into Profile, and no field was added to
`User`.

## 2. Behavioral personalization stays in source domains

The temptation this phase resisted: a `Profile.interests` column
"summarising" behavior. It would be a counter with no owner  stale the
moment a favorite lands, and a second source of truth for taste.
Recommendation already reads behavior through each source's own
selectors (ADR 0018 §2); explicit taste flows separately through the
users fact. The two signals meet only inside the recommendation scorer.

## 3. Recommendation consumes a fact, not profile state

`PersonalizationFact` (Phase 12, extended here with
`preferred_language`) remains the single crossing point: a frozen
dataclass of exactly what the user explicitly supplied  experience
level, favourite-category slugs, preferred language. Never inferred
interests, never counts, never privacy-gated fields; a consumer cannot
leak what it never receives. Recommendation's pipeline is untouched 
the same deterministic scorer consumes the fact when present and
degrades to cold start when empty (verified against ADR 0018 §6).

## 4. The favourite-category backfill  a promise kept

Phase 1 stored favourite categories as canonical slugs with a docstring
promising "becomes a many-to-many to `recipe_categories` once that app
exists" (ADR 0006). Phase 14 executed it exactly as designed: migration
`users.0002` links every stored slug to its (Phase 2-seeded) taxonomy
row and drops the JSON column. What changed in behavior:

- **Validation is the live taxonomy**, not a frozen enum  an
  admin-added category is selectable with no code change; `resolve_slugs`
  returns active categories only, and the diff is this app's own error.
- **A deleted category self-heals**  the through rows cascade, so no
  profile carries a dangling slug.
- **Duplicates are impossible** by the through-table pair; `.set()` is
  idempotent.
- **The API shape did not change**: a sorted list of slugs, both ways.

`users → recipe_categories` is a new reference direction (the foundation
app referencing a content app) and is accepted deliberately: the
taxonomy is platform vocabulary, the reference is the same one the JSON
slugs always made informally, and `recipe_categories` imports nothing
from users  no cycle can form. `BakingCategory` survives only because
the Phase 2 seed migration imports it.

## 5. Privacy through one projection

Unchanged, on purpose: `get_visible_profile` remains the single place
privacy is decided  it returns a `PublicProfileDTO` with the owner's
settings already applied, so the public serializer contains zero
conditional logic and *cannot* leak what the DTO does not carry. Phase
14 added leak tests (email, locale, theme, notification flags,
`is_staff` never appear in any public payload) rather than a second
mechanism.

## 6. Settings stay split by owner

Learning/privacy/interface preferences → `users`. Per-event in-app
notification preferences → `notifications` (Phase 10). Conversation
language per conversation → `assistant`. Ranking policy →
`recommendation`. The Phase 1 `email_*` flags on `UserPreference` are
**email-channel** opt-ins predating the notifications app and do not
collide with its per-event in-app rows; when the email-delivery phase
lands they are its natural migration candidates  recorded here, not
"fixed" now.

## 7. `/me/settings/` is a composition, not an owner

One read for the settings screen: profile, preferences, the
notifications app's own `effective_preferences`, and derived completion.
It is GET-only  structurally incapable of becoming an owner  and each
block is produced by its owning domain's public boundary (the favorites
card-stitching pattern applied to settings). The one architectural cost,
a `users.api → notifications.selectors` import, is confined to the API
edge and cannot cycle (notifications imports nothing from users).
Writes keep going to the owners' endpoints, verified by e2e.

## 8. Thai-first language, one field

`UserPreference.locale` was free text (`"en-us"` default) that nothing
consumed  on a Thai-first platform, the wrong default on a dead field.
It is now the platform's one language preference: choices exactly equal
to `AssistantLanguage` (`th`/`en`  a test pins the sets equal, so no
translation glue can ever be needed), default `th`. Existing values
mapped by language family (`th*` → `th`, else `en`), preserving the only
information the old field carried. No second language field anywhere.
Thai text (names, bios, locations, emoji) round-trips untouched  no
ASCII normalisation exists in the path, and e2e proves it over HTTP.

## 9. Profile vs account boundary

Unchanged and now documented: account operations (password, email
verification, activation, authentication) live under `/auth/` and
`/users/account/`; profile operations under `/users/profile/` with a
service-side allow-list (`PROFILE_EDITABLE_FIELDS`) so email, staff
state, timestamps, rewards, achievements and progress are unreachable
from the profile surface by construction  separate write serializers
per ADR 0007's mass-assignment reasoning.

## 10. Completion is derived; queries are pinned

`profile_completion` is a pure function over six intent-bearing fields
(`experience_level` excluded  its non-empty default carries no signal);
no counter column, nothing to drift, privacy settings do not affect the
owner's own count. Query pins: own profile read 2 (row + prefetched
categories), public profile 2, personalization fact 2, `/me/settings/` 4
beyond session auth  all `assertNumQueries`-enforced, bounded regardless
of category count.

## 11. Future personalization seams

Profile badges and learner statistics: read-side compositions over
certificates/gamification facts, joining the settings pattern. Learning
goals and preferred lesson formats: new `UserPreference` columns when a
consumer exists. Recommendation explanations already flow through reason
codes (ADR 0018 §10); personalization controls ("stop using my
favorites") would become one boolean the fact respects. Onboarding can
read `profile_completion.missing` as its checklist. None of these got
speculative columns today.
