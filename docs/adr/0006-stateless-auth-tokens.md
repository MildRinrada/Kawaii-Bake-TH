# 0006 — Stateless Tokens for Verification and Password Reset

- **Status:** Accepted
- **Date:** 2026-08-07

## Context

Phase 1 is constrained to three tables: `User`, `Profile`, `UserPreference`.
The Phase 0 database draft proposed `EmailVerification`, `PasswordReset` and
`LoginHistory` tables. Email confirmation and password reset still have to work.

## Decision

Use signed, stateless tokens. No token tables.

- **Password reset** uses Django's `PasswordResetTokenGenerator` with a project
  specific `key_salt`. Its hash includes the password hash and `last_login`, so
  a token dies the moment the password changes or the user signs in.
- **Email verification** subclasses it with a **different `key_salt`** and a
  hash of `(pk, email, is_email_verified, timestamp)`.

Three details are load-bearing:

1. **Different salts per token type.** A shared salt would let a reset token be
   replayed as a verification token.
2. **The verification hash excludes the password and `last_login`.** Django's
   default includes both, which would invalidate a verification link as soon as
   the user signs in — an extremely common sequence (register → sign in → open
   email). Hashing `is_email_verified` instead keeps the token single-use: it
   stops validating the instant verification succeeds.
3. **`check_token` is reimplemented for verification.** The stock method reads
   `settings.PASSWORD_RESET_TIMEOUT` directly, so a subclass cannot otherwise
   have its own lifetime. The override reads `EMAIL_VERIFICATION_TIMEOUT` and
   still honours `SECRET_KEY_FALLBACKS`, so key rotation does not invalidate
   every outstanding link.

Related rules: verification never signs the user in (a forwarded email must not
become a session), and `/password-reset/` always returns 202 so it cannot be
used to test whether an address is registered.

## Consequences

- Zero schema, zero expiry sweeps, zero cleanup jobs.
- Tokens self-invalidate on use; there is no revocation list to maintain.
- **`LoginHistory` is genuinely lost.** Sign-ins go to the `kawaiibake.security`
  logger with user id and IP, but there is no queryable audit trail and no
  "active devices" screen. If either becomes a requirement, that table must be
  added — this is a known gap, not an oversight.
- Token lifetimes are governed by `PASSWORD_RESET_TIMEOUT` (1 hour) and
  `EMAIL_VERIFICATION_TIMEOUT` (7 days).
