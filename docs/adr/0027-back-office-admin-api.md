# ADR 0027 - The back-office admin API

- **Status:** accepted
- **Date:** 2026-08-10
- **Phase:** back-office completion

## Context

The `/admin` frontend existed as a shell: recipes, courses, quizzes and
security had real management screens, but categories, users,
achievements, favorites and cross-content review moderation could only
render an "endpoint missing" panel and point at Django admin. Operating
the platform meant leaving the platform.

Category tile photos were a second, quieter problem: the home page's
"explore by category" boxes were a hardcoded slug→file map in the
frontend, so a category added by an operator rendered the generic
"other" art forever.

## Decisions

### 1. One convention for every staff surface

Every new endpoint follows the security-app pattern (ADR 0025): mounted
under `/api/v1/admin/<domain>/`, but the prefix is **naming only** -
every view declares `IsAdminUser` itself, so a re-mount can never expose
one. Reads are selectors, writes are services with an `actor_id` audited
into the log line; nothing new appears in the HTTP layer.

The strict `PaginatedFilterSerializer` moved from `apps.security` to
`apps.common` so every roster/list endpoint rejects a typo'd filter with
a 400 instead of silently returning an unfiltered page.

New surfaces: `admin/recipe-categories/` (full CRUD),
`admin/users/` (roster + staff edits), `admin/achievements/` (badge CRUD
+ read-only award ledger), `admin/reviews/` (flat cross-content list),
`admin/favorites/` (cross-user list + live top-ten rankings).

### 2. Categories own their tile photo

`RecipeCategory.image` (ImageField, byte-validated like every upload,
SVG excluded) with `image_url` on the public serializer. The frontend's
built-in artwork became the *fallback*: a fresh database still looks
finished, an operator's upload wins everywhere the tile renders. Slugs
derive from the Thai name when omitted; renames are CI-collision-checked
(`duplicate_category_slug`, 409). Deleting a category only unlinks
M2M assignments - content is never deleted with its taxonomy.

### 3. Staff manage accounts, but not their own keys

`PATCH /admin/users/{id}/` edits the legal name, suspension
(`is_active`, maintaining `deactivated_at` exactly like self-service
deactivation), the staff flag, and `is_email_verified` - an **emergency
override** for verification mail that never arrives, stamping/clearing
`email_verified_at` exactly like the self-service flow so the audit
trail stays truthful. Two guards live in the service, not the UI:
nobody edits their own access flags (the last operator must not be able
to lock themselves out alone), and superuser flags are untouchable from
the API (`protected_account`, 403). The roster serializer carries PII
(email, legal name) deliberately - it is unreachable without `is_staff`.

### 4. Moderation verbs are visibility and existence, never content

The flat review list and the gallery status filter give staff a queue,
but the mutation verbs stay the existing owner-or-staff `PATCH
status`/`DELETE` routes. There is deliberately no endpoint that edits
someone else's words - a review body or post caption belongs to its
author. The same rule shaped the community feed's owner controls: users
hide/edit/delete their own posts (feed card + detail page), admins only
hide or delete.

### 5. Badges gained CRUD; the award ledger did not

`BadgeDefinition` rows are now staff-curated over HTTP ("deliberately no
CRUD API" in the model docstring is repealed), but `Achievement` stays
append-only (ADR 0012): the ledger is listable (`awards/`), never
grantable or revocable. Deleting an awarded badge trips the FK's
PROTECT and maps to `badge_in_use` (409) - retiring earned presentation
is done by deactivating, which hides the badge from the catalogue
without un-earning anyone's fact.

### 6. Favorites are readable in aggregate, writable by no one

Staff see the cross-user list and live most-favorited rankings
(computed, never stored - the no-counters rule). There is no admin write
path: a favorite is a user's private signal, and deleting one would be
editing someone's taste.

## Consequences

- Django admin is no longer required for day-to-day curation; it remains
  the escape hatch for superuser management and data surgery.
- Category art now has two sources (upload, then built-in fallback);
  the frontend must keep the fallback path alive for fresh installs.
- The award ledger being read-only means a mis-awarded achievement is
  fixed in the shell, not the UI - accepted, because a revoke endpoint
  is a bigger integrity risk than the rare mistake.
- New E2E/API coverage pins the permission gates (401/403 on every
  route), the self/superuser guards, slug conflicts, the PROTECT
  mapping, and that the gallery status filter can only narrow.
