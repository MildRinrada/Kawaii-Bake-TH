# 0007  Session Cookies for Phase 1, Behind a Credential Seam

- **Status:** Accepted
- **Date:** 2026-08-07

## Context

The requirements list login and logout as "implement now" and JWT with refresh
tokens as "prepare architecture for". A Next.js SPA is the client, which makes
bearer tokens the conventional choice  but the project is also constrained to
three tables, and "logout" has to mean something.

## Decision

**Phase 1 authenticates with Django session cookies (httpOnly),** placed behind
a `CredentialIssuer` seam so switching to JWT is a one-module change.

### Why not JWT now

| | Session cookie | `simplejwt` |
|---|---|---|
| Logout | Server-side, immediate, per-device | Access tokens are un-revokable; logout is a client-side lie |
| Extra tables | none | `token_blacklist` adds two, plus a flush cron |
| XSS | JavaScript cannot read the cookie | A token in `localStorage` means any XSS is total account takeover |
| Cross-origin | Needs CORS + CSRF + `SameSite` planning | Simpler  the one genuine advantage |

Every session downside is a configuration problem; the JWT downsides are
architectural. Storing a refresh token in an httpOnly cookie  the usual fix 
is reinventing sessions with extra steps.

### The seam

```
apps/authentication/api/credentials/
├── base.py            CredentialIssuer protocol + IssuedCredential
├── session_issuer.py  Phase 1  the ONLY module importing auth.login/logout
└── jwt_issuer.py      reserved
```

`settings.AUTH_CREDENTIAL_ISSUER` selects the implementation. Views resolve it
through `get_credential_issuer()` and never import a concrete class.

Two decisions make the future swap free:

- `login()` is always called with an explicit `backend=`. Adding a second
  backend to `AUTHENTICATION_BACKENDS` is exactly what breaks projects that
  relied on the implicit single-backend case.
- `IssuedCredential.status` ships now (`authenticated` / `mfa_required`), so
  adding 2FA later is additive rather than a breaking response-shape change.

`/api/v1/auth/token/refresh/` is reserved in the URL conf.

## Consequences

- Real logout, no new tables, credential unreadable to JavaScript.
- Sign-in-related settings already in `base.py` (`SESSION_ENGINE`,
  `SESSION_COOKIE_AGE`, remember-me via `set_expiry`) stay meaningful.
- **CSRF must be handled explicitly.** DRF `csrf_exempt`s every `APIView`, and
  `SessionAuthentication` enforces CSRF only for already-authenticated
  requests  so unauthenticated POST endpoints inherit `CsrfProtectedAPIView`.
  There is a test asserting login fails without a token.
- **Deployment constraint.** `SameSite=Lax` requires the frontend and API to
  share a registrable domain (`app.kawaiibake.com` + `api.kawaiibake.com`).
  Locally, `localhost:3000 → :8000` is same-site, so a mismatch will not surface
  until deploy. If a shared domain cannot be guaranteed, switch the issuer to
  JWT rather than setting `SameSite=None`, which Safari ITP and Firefox
  partition or block.
- **OAuth will need a table** (`provider`, `provider_uid`, user FK). The
  three-table rule cannot cover it; noted now rather than discovered in Phase 4.
  Social-only accounts use `set_unusable_password()`, and the password-reset
  selector already excludes them.
