# Security Policy

Thank you for taking the time to look at the security of KawaiiBake. This
document explains what is in scope, how to report a vulnerability, and what
happens after you do.

KawaiiBake is a personal portfolio project maintained by one person. The
response times below are what a single maintainer can honestly commit to, not
a commercial support agreement.

## Supported Versions

This project has no tagged releases. Security fixes are applied to the
`main` branch only, and only `main` is supported.

| Version | Supported |
| ------- | --------- |
| `main`  | Yes       |
| Any fork or older commit | No |

If you run a fork, rebase onto `main` before reporting — the issue may already
be fixed.

## Reporting a Vulnerability

**Do not open a public issue, pull request, or discussion for a security
problem.** A public report tells everyone about the flaw before there is a fix.

Report privately through GitHub instead:

1. Go to the **Security** tab of this repository.
2. Click **Report a vulnerability**.
3. Fill in the advisory form.

This opens a private advisory visible only to you and the maintainer. GitHub
notifies the maintainer directly, and the report stays private until it is
published.

If the **Report a vulnerability** button is not visible, private reporting has
not been enabled yet on the repository. In that case, open a regular issue that
says only *"I would like to report a security issue privately"* — with no
technical detail, no reproduction steps, and no affected paths — and wait to be
contacted.

### What to include

A report is much faster to act on when it contains:

- **What the issue is** — the vulnerability class (stored XSS, IDOR, auth
  bypass, SSRF, …) and a one-line summary.
- **Where it is** — the affected endpoint (`/api/v1/…`), file path, or UI
  screen. A `path/to/file.py:42` reference is ideal.
- **How to reproduce it** — exact steps, request bodies, and the account state
  required (anonymous, authenticated learner, staff).
- **What an attacker gains** — reading another user's data, escalating to
  staff, executing script in someone's browser, and so on.
- **Your environment** — commit SHA, `DJANGO_SETTINGS_MODULE`
  (`development` / `production`), database, and browser where relevant.

Proof-of-concept code, a curl command, or a short screen recording all help.
Please keep any proof-of-concept private until a fix ships.

### What to expect

| Stage | Target |
| ----- | ------ |
| Acknowledgement that the report arrived | Within 5 business days |
| Initial assessment (valid / not valid, rough severity) | Within 14 days |
| Fix for a confirmed high-severity issue | As soon as practical, prioritised over feature work |
| Advisory published | After the fix lands on `main` |

You will be told when the report is accepted, when it is rejected and why, and
when a fix is merged. If a report goes quiet for longer than the targets above,
a polite nudge on the advisory thread is welcome.

Credit is given in the published advisory by default. Say so in your report if
you would rather stay anonymous.

## Scope

### In scope

Source code in this repository:

- The Django backend — `apps/`, `config/`, `ai/`, `infrastructure/`
- The Next.js frontend — `frontend/`
- Docker and deployment configuration — `docker/`, `requirements/`
- Anything committed here that should not have been, such as a real secret,
  credential, or private key

### Out of scope

The items below are either not defects, not this project's to fix, or already
documented as deliberate. Reports about them will be closed with a pointer back
to this section.

- **Third-party dependency vulnerabilities.** Report those to the upstream
  project. A report *is* in scope if you can show a working exploit path
  through KawaiiBake's own code, or that this project pins a version known to
  be vulnerable in a way that is actually reachable here.
- **Findings from an automated scanner with no demonstrated impact.** Raw
  scanner output without a reproduction and an explained consequence is not
  actionable.
- **Missing security headers or relaxed settings under the development
  configuration.** `config/settings/development.py` is deliberately permissive
  for local work. Evaluate `config/settings/production.py` instead.
- **Denial of service, volumetric, brute-force, or load testing.** Never run
  these. The platform is a learning project with no capacity to absorb them.
- **The client-side developer-tools guard** (`apps/security`,
  `SECURITY_CLIENT_GUARD_MODE`). It is explicitly documented as a signal source
  and a speed bump, *not* a security boundary — see
  [ADR 0025](docs/adr/0025-threat-watch-and-client-guard.md), section 8.
  "DevTools can be opened anyway" and "the JavaScript can be read" are known
  and accepted. Anything shipped to a browser is public.
- **Self-XSS**, and attacks that require the victim to paste attacker-supplied
  code into their own console.
- **Social engineering, phishing, or physical access** against the maintainer
  or any user.
- **Missing rate limits on endpoints that already require authentication**,
  unless you can show concrete abuse.
- **Best-practice suggestions with no exploit path.** These are welcome, but as
  a normal public issue rather than a security report.
- **Any deployment of KawaiiBake that you do not own.** If you find a hosted
  instance run by a third party, report it to whoever operates it.

## Testing Guidelines

Test against **your own local installation only**. The README has full setup
instructions; a local install takes a few minutes and gives you superuser
access, which is far more useful for testing than probing a live host.

Do not test against any host you do not own or have written permission to test.
Do not access, modify, or retain another person's data. If you encounter
personal data by accident, stop, do not save it, and say so in your report.

Note that this repository ships a request watcher (`apps/security`) that scores
probing behaviour and can block an address when `SECURITY_AUTO_BLOCK` is
enabled. Testing locally means you will only ever trip your own instance.

## Current Security Posture

Provided so you can tell an intentional design from an oversight. None of this
is a guarantee of correctness — if you can break any of it, that is exactly the
kind of report this policy is asking for.

**Authentication and sessions**

- Session cookies are `HttpOnly` with `SameSite=Lax`, and `Secure` in
  production. Tokens are deliberately not stored in `localStorage` — see
  [ADR 0007](docs/adr/0007-session-auth-for-phase-1.md).
- Passwords are hashed with Argon2 in production, and validated against
  Django's similarity, minimum-length, common-password, and numeric-only
  validators.
- Sign-in, registration, password reset, verification resend, and
  username-availability checks are all rate limited per address.
- Password reset is written to avoid acting as a user-enumeration oracle.
- Google Sign-In is optional and disabled unless a client ID is configured.

**Transport and browser hardening (production settings)**

- HTTPS redirect, HSTS for one year with `includeSubDomains` and `preload`.
- `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`,
  `Referrer-Policy: same-origin`.
- CSRF protection with an explicit trusted-origin list; CORS uses an explicit
  allowlist with credentials, never a wildcard.

**Application boundaries**

- The backend is API-only and authorises every read and write server-side.
  Client-side gating — including staff-only admin screens — is a rendering
  decision only; see [ADR 0022](docs/adr/0022-admin-surface-identity-flag.md).
- Uploaded images are restricted to JPEG, PNG, and WebP. SVG is rejected
  deliberately, because it can carry script and would become stored XSS.
- Secrets are read from the environment. `.env` files are git-ignored; only
  `.env.example` is committed.

## No Bug Bounty

This is an unpaid personal project. There is no bounty, no swag, and no payment
of any kind. What is offered is a genuine reply, a fix, and public credit if you
want it.
