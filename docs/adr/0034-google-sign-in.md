# ADR 0034 - Google sign-in, and the first table authentication owns

- **Status:** accepted
- **Date:** 2026-08-12
- **Phase:** Sign-up rework

## Context

Sign-up asked for five fields and offered one way in. Two of those fields
- ชื่อจริง and นามสกุล - existed to print certificates (they moved to
issuance; see `docs/API.md`, `legal_name_required`), and the design
review that removed them named the missing social button as the single
biggest remaining drag on conversion. ADR 0007 anticipated this exact
request and recorded what it would cost: "if OAuth or social login is
added later it *will* need a provider-link table; that is a deliberate,
documented exception".

This ADR spends that exception, and records the three decisions that are
not obvious once you do.

## Decisions

### 1. The subject id is the identity; email is matched exactly once

`SocialAccount(provider, provider_uid, user)` with a unique constraint on
`(provider, provider_uid)`. Every sign-in after the first resolves
through that row and reads nothing else.

Matching on email instead would be a live account-takeover path: mail
addresses get released and re-issued (corporate domains do this
routinely), and whoever received the address next would sign in as its
previous owner. Email is used exactly once - when a Google identity first
meets an existing local account - and only because Google states it
verified the address in the same signed token. `email_verified` false is
a refusal (`social_email_unverified`), not a warning.

The account's address may later change at Google; the subject does not,
so a moved address still lands on the same account. That is asserted in
`test_the_subject_decides_even_when_the_address_changed`.

### 2. Verification is delegated, the audience check is not

The ID token is verified by Google's `tokeninfo` endpoint rather than
locally against its JWKS. That trades one HTTPS round trip per sign-in
for no key cache, no clock-skew handling, and no cryptography of ours to
get wrong. `_fetch_token_info` is the only place that talks to Google, so
swapping in local verification later touches one function and no tests.

What delegation cannot cover is **audience**: a real, unexpired,
correctly-signed Google token minted for *someone else's* application
passes verification and must still be refused here. So the service checks
`aud == GOOGLE_OAUTH_CLIENT_ID` and `iss ∈ {accounts.google.com,
https://accounts.google.com}` itself. Both have tests, because both are
the kind of check that is easy to delete by accident and impossible to
notice missing.

Every rejection reason collapses into one code (401 `social_auth_failed`).
The caller can do exactly one thing about all of them, and a taxonomy of
refusals is free reconnaissance for whoever is probing.

### 3. Unconfigured means absent, not broken

`GOOGLE_OAUTH_CLIENT_ID` empty (the default, and the state of this repo
as shipped) disables the feature: the endpoint answers 503
`oauth_unavailable`, and the frontend - reading its own
`NEXT_PUBLIC_GOOGLE_CLIENT_ID` - renders no button, no divider, nothing.

A dead button is worse than no button, and a *demo* button that pretends
to work is worse than both. The two ids must be the same value, which is
why the 503 exists at all: it is what a mismatch between the two halves
of the configuration looks like, and that is worth an explicit answer
rather than a 404.

### 4. Accounts made this way have no password, and do have consent

Provider-created accounts get `set_unusable_password()`, which
`user_selector.get_for_password_reset` already filters out - so a
social-only account can never be sent reset mail for a password it does
not have. The handle is derived from the mail name and made unique
through the same validator a typed handle passes, so reserved words
(`admin@gmail.com` → not `admin`) cannot be claimed sideways.

`terms_accepted_at` is stamped at creation. The button sits under a line
saying that continuing accepts the terms, and PDPA consent has to be an
act the person takes - pressing that button, under that line, is the act.
Registration by password keeps its explicit checkbox.

## Consequences

- One new table, `auth_social_account`, in the app that had none. The
  model docstring says why it could not be stateless.
- `POST /auth/google/` returns **201** when it created the account and
  **200** when it signed one in - one endpoint, because the visitor
  pressed one button and does not know which case they were.
- Unlike password registration, this path *does* establish a session
  immediately: the provider already proved the address, so there is no
  inbox step left to wait for.
- Adding a second provider is now additive: a `SocialProvider` member, a
  verification function, and nothing else.

## Alternatives considered

**django-allauth.** Brings templates, its own URLs, its own account model
and a migration surface far larger than the one table actually needed;
this codebase's auth is deliberately hand-rolled around ADR 0007's
credential-issuer seam, and allauth would own that seam instead.

**Authorisation-code flow with a client secret.** Correct for a server
that renders HTML, wrong here: the frontend is a separate origin, the
redirect dance would have to bounce through it, and the browser flow's
signed ID token already gives the same guarantee with no secret to keep.

**Matching accounts on email alone (no link table).** Stateless, and the
takeover path in decision 1 is exactly why not.
