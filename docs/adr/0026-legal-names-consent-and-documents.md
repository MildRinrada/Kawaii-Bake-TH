# ADR 0026 - Legal names, PDPA consent, and editable legal documents

- **Status:** accepted (decision 1 amended by [0035](0035-legal-name-at-issuance.md))
- **Date:** 2026-08-10
- **Phase:** legal & identity hardening

## Context

Certificates print a student's name, and until now that name fell back to
the profile display name or the raw handle - a credential naming
"mildbakes" is not a credential. At the same time the platform collected
personal data with no recorded consent and no readable terms, which PDPA
(พ.ร.บ.คุ้มครองข้อมูลส่วนบุคคล พ.ศ. 2562) does not permit, and the legal
text itself needed to be editable by operators without a deploy.
Registration also signed users in with an unverified email address.

## Decisions

### 1. The legal name lives on `User`, required at registration

`first_name` / `last_name` are PII in the same class as `email`: stored on
the account, served only to the owner (`GET /users/profile/`), never on
any public payload - the public-profile exact-keys test enforces that.
The registration serializer makes them mandatory; the model keeps
`blank=True` because pre-existing accounts predate the rule. A data
migration backfills the known development accounts (and a readable
handle-derived stand-in for the rest), so the certificate path never
regresses to handles.

Certificate issuance snapshots `legal name → display name → username`
(the fallbacks exist only for pre-rule accounts). Already-issued
certificates keep their immutable snapshot.

### 2. Consent is an explicit action, stamped once

`accept_terms` must be `true` in the registration payload - rejected as a
field error otherwise - and reaching the registration service *is* the
consent event: `User.terms_accepted_at` is stamped there, giving PDPA its
evidence. The consent line on the form links to the documents it names.

### 3. `apps.legal`: four documents in the database, staff-editable

`LegalDocument` holds one row per kind (`terms`, `privacy`, `pdpa`,
`cookie`) - a closed enum, because consent language and routing reference
these slugs. Reads are public (`GET /legal/`, `GET /legal/{kind}/`):
someone deciding whether to register must be able to read what they are
agreeing to. Writes are `IsAdminUser` PATCHes on the same detail route;
every content change bumps `version` via an F-expression (no lost update
between concurrent editors), which keeps "which text was live when this
user consented" answerable against `terms_accepted_at`.

Bodies use a deliberately tiny rich-text format (`##` headings, `-`/`1.`
lists, `**bold**`, `*italic*`, `__underline__`) parsed into React
elements on the frontend - never HTML, so the admin editor cannot become
a stored-XSS vector into a public page.

### 4. Registration no longer signs in

The flow is now register → check-your-inbox screen → emailed link
(`/verify-email/{uid}/{token}`) → explicit confirm button (a scanner
prefetching the link must not consume it) → `/login?verified=1` with a
one-time banner. Signing in is the user's own act after verification.

## Consequences

- New E2E coverage pins: consent and name are required, registration does
  not start a session, the verified banner renders, and legal documents
  edit-and-version round-trip.
- The resend-verification endpoint requires a session, so the
  check-your-inbox screen deliberately has no resend button - signing in
  later offers it from settings. A future anonymous resend endpoint could
  lift this.
- `is_staff` was added to the own-profile payload (ADR 0022 pattern) so
  the shell can render the back-office shortcut; it grants nothing.
