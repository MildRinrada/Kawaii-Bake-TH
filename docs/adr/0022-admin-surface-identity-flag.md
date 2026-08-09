# ADR 0022 — The admin surface reads one flag; authorization stays server-side

- **Status:** Accepted
- **Date:** 2026-08-09
- **Supersedes:** nothing
- **Superseded by:** nothing

## Context

The frontend gained an admin surface (`/admin/*`) built entirely on the
existing API. Every staff capability the platform has was already there
before this change:

- staff-widened reads through the existing `scope=all` parameter
  (recipes, courses, quizzes, questions) and through `viewer_is_staff`
  in the visibility selectors;
- staff moderation writes on content the caller does not own — review
  `status` PATCH, question/thread/answer PATCH and DELETE, gallery post
  PATCH and DELETE, recipe/course/quiz `publish|unpublish|archive`;
- one genuinely staff-only endpoint, `POST /rewards/adjustments/`
  (`IsAdminUser`).

What did **not** exist was any way for a client to know whether the
caller is staff. `MeSerializer` carried identity but no authorization
state, and no other payload exposes the flag. Without it the admin shell
has three bad options: render itself to everyone and let each page fail
piecemeal; probe a staff-only endpoint (the only one is a *write* — an
auditable balance adjustment, so probing is out of the question); or
infer staff status from the fact that `scope=all` silently returns more
rows, which is unobservable without a second reference request and
wrong the moment a non-staff account happens to own everything.

## Decision

Add a single read-only boolean, `is_staff`, to the `/api/v1/auth/me/`
payload (`MeDTO` → `MeSerializer`).

It is deliberately placed on the *authentication state* endpoint rather
than on `/users/profile/`: the profile payload describes a person, this
flag describes a session's authority. No new endpoint is introduced.

The flag is **presentation input only**. It decides whether the admin
chrome renders. It grants nothing:

- every staff-widened read still resolves `viewer_is_staff` from
  `request.user` server-side;
- every moderation write is still authorised in the owning app's
  service;
- a non-staff caller who types `/admin/recipes` and defeats the client
  check sees exactly the public catalogue, because `scope=all` silently
  narrows for non-staff (Phase 2 rule, unchanged).

## Consequences

**Positive**

- The admin shell can refuse to render, and can say *why* (401 vs 403),
  instead of presenting controls that 403 on click.
- No new endpoint, no new permission class, no business logic moved to
  the client.

**Negative / accepted**

- The payload now tells a caller something about their own privileges.
  This is not a disclosure: the caller can already observe it by
  performing any staff action. It says nothing about any other account.

**Rejected alternatives**

- *A dedicated `/admin/…` API namespace.* The capabilities already
  exist on the domain endpoints; a parallel namespace would duplicate
  visibility rules — precisely the drift ADR 0008 exists to prevent.
- *Adding `is_staff` to `OwnProfileSerializer`.* The profile is public-
  facing data about a person and is consumed by the learner UI; an
  authorization flag does not belong in it.
- *Inferring staff from response shape.* Unreliable and untestable.

## Known gaps this ADR does not close

The admin UI documents, in the interface itself, the operations that
have no API and are therefore not offered:

| Missing capability | Consequence for the admin UI |
|---|---|
| No user list / user detail admin endpoint (only `GET /users/{username}/`, a public profile) | Users page is lookup-only; no roster, no activation toggle |
| No endpoint exposes `certificate_service.revoke()` | Certificates page is read-only; revoke is not offered |
| No cross-user reads for progress, certificates, achievements, favorites, notifications, assistant conversations or recommendations (all are `me`-scoped) | Those admin pages show the caller's own data and state plainly that a platform-wide view needs a backend endpoint |
| No global reviews list (reviews are listed per recipe/course) | Review moderation is reached through a content item, not a flat queue |
| No write endpoints for `recipe_categories` | Categories page is read-only |

Closing any of these is a backend phase, not a frontend workaround.
