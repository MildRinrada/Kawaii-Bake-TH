# ADR 0031 - The user-management workspace and staff account actions

- **Status:** accepted
- **Date:** 2026-08-11
- **Phase:** back-office completion, part five

## Context

`/admin/users` was a roster with a detail drawer. Operators wanted a
real workspace: summary numbers, an activity column, account creation,
password-reset/verification emails on demand, and bulk actions - while
the redesign spec's "roles" (learner/creator) do not exist in the data
model, and no delete endpoint exists at all.

## Decisions

### 1. Account *lifecycle* stays in users; account *actions* live in authentication

Creating an account, sending a reset link and re-sending verification
mint credentials and email flows, so they live in
`apps.authentication.staff_account_service` - the dependency direction
(`authentication → users`) stays one-way. They mount under the roster's
`/admin/users/` prefix via a second include: URL prefix is config, not
coupling (the ADR 0009 lesson, reapplied).

- **Create** runs the registration validation pipeline minus the rate
  limit (the caller is staff) and minus the terms stamp - the member
  never consented, so `terms_accepted_at` stays empty until they do.
  `verified: true` stamps the address (the operator vouches for it);
  otherwise the normal verification email goes out.
- **Reset / resend** report ineligibility honestly (409
  `not_applicable`): the anonymous reset endpoint stays silent to avoid
  being an account oracle, but staff already see the roster - silence
  would only hide failures.

### 2. Roles and activity are honest to the data model

There is no stored learner/creator role, so the UI shows what is real:
ผู้ดูแลสูงสุด / ผู้ดูแล / สมาชิก from the flags, and "creator-ness" as
activity counts. The roster annotates `recipes_count`,
`courses_count` (non-dropped enrollments) and `posts_count` in one
queryset (`Count(..., distinct=True)` across the multi-join) - a
staff-only aggregation seam over reverse relations; only constants
cross the app boundary and nothing public renders these numbers.

### 3. Bulk is orchestration, not pretense; delete does not exist

Bulk deactivate/reactivate/resend run one real call per selected row,
sequentially, skipping ineligible rows (the caller's own account,
superusers, already-in-state) and reporting the batch per-name. There
is no bulk endpoint and no delete anywhere: deactivation is the
platform's soft path, content and history stay, and the page says so
instead of hiding it.

### 4. Summary cards are filters

`GET /admin/users/stats/` feeds four cards (total / active / pending =
active-but-unverified / suspended) and clicking one applies the same
narrow filters the toolbar offers - one population definition shared by
the number and the list it drills into.

## Consequences

- `usePagedList` now lets a caller-supplied `page_size` win over the
  hook default, which is how the rows-per-page select works everywhere.
- Staff-created accounts appear with an initial password chosen by the
  operator; the reset-link action is the recommended handover.
- E2E pins: stats cards, bulk bar on selection, create form, drawer
  activity counts and email actions - plus a live probe of the full
  create → deactivate → reactivate loop through the UI.
