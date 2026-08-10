# ADR 0025 — Threat watching, and the honest limits of a client-side guard

- **Status:** Accepted
- **Date:** 2026-08-09
- **Supersedes:** —
- **Related:** [0005](0005-api-only-backend.md) (API-only backend),
  [0016](0016-notifications-as-a-push-sink.md) (leaf sink apps),
  [0022](0022-admin-surface-identity-flag.md) (`is_staff` on `/auth/me/`)

## Context

The platform had no way to tell whether anyone was probing it. Django's
logs record every request identically, so a `sqlmap` sweep and a learner
browsing recipes look the same to anybody reading them, and nothing
aggregates repeated behaviour from one source.

Three capabilities were asked for:

1. Detect crawling, scripted access and probing of paths that do not
   exist (`/.env`, `/backup.sql`, …).
2. Score that behaviour and summarise it as **low / medium / high /
   critical**, with filters, on an admin page.
3. Make the browser's developer tools unavailable to ordinary visitors,
   switchable from the environment, with signed-in users exempt.

(1) and (2) are ordinary, well-understood server-side work. (3) is not
achievable as stated, and the difference has to be recorded rather than
quietly papered over.

## Decision

### 1. A leaf app, `apps.security`, that nothing imports back

The app holds two models, one middleware and nine endpoints. It imports
no feature domain and no feature domain imports it. The only way in is
the middleware, which sees a request as `(ip, path, query, method, user
agent)` — no recipes, no courses, no user profile. That is what lets a
watcher sit at the edge of every request without coupling the platform to
it, and what lets the whole app be deleted in one commit if it ever
becomes a liability.

### 2. Detection is pure functions over strings

`detectors/request_rules.py` takes strings and returns a `Signal | None`.
No `HttpRequest`, no ORM, no settings. Detection rules are the part of
this app most likely to be wrong — a false positive scores a real learner
and a false negative misses a scan — so they are the part that must be
testable with one function call and no database. Both directions are
asserted: Thai-language recipe searches and Googlebot are checked to
produce *nothing*, alongside the positive cases.

**One request produces at most one observation.** `inspect_request`
returns the single worst match rather than every match. `curl` fetching
`/.env` with an injection payload trips three rules; scoring it three
times would let one packet reach *critical* on its own.

### 3. Scoring: exponential decay, not a rolling window

A profile's score is `decayed(previous) + weight`, halving every 12
hours. The alternative — summing events inside a fixed window — needs a
sweep job to age rows out, and gives a cliff where an address drops from
*critical* to *low* because one event crossed a boundary. Decay ages
correctly with no scheduled work at all, even for a profile nobody reads
again for a month.

Weights and thresholds are constants in one file so an operator can
answer "why is this address *high*?" by reading, not by tracing. The
calibration claim — one unambiguous probe reaches *high*, two reach
*critical* — is asserted in `test_scoring.py` rather than left in a
comment.

The `critical` floor is **85**, deliberately just under two honeypot hits
(2 × 45). Decay is applied before every increment, so a score that should
land exactly on a threshold lands a hair below it; a floor placed on the
nose makes the band flap on floating-point rounding.

### 4. `ThreatProfile` is a cache, and there is a command that proves it

`score`, `level` and `event_count` are derived from the events beneath
them. They are stored because recomputing a decayed sum over every event
on every dashboard render does not scale and because filtering by band
needs an index. `manage.py recount_threats [--dry-run]` replays the event
log and reports drift; the correct output is "0 drifted profiles".

`score` and `level` are only ever written together, so they cannot
disagree.

### 5. Events are append-only; profiles are the mutable part

An event is evidence, and evidence that can be rewritten is worthless in
an incident review. There is no update path, no delete endpoint, and the
Django admin registration is read-only. An event's `severity` is the band
its **own weight** rates — one honeypot hit stays *high* even after the
address later reaches *critical* — so re-tuning the weights cannot
retroactively rewrite what the platform observed.

Operator triage (`review_state`, `blocked_until`) lives on the profile,
records who did it, and changes no score.

### 6. Blocking is time-boxed, off by default, and cached

- Automatic blocking is **off** unless `SECURITY_AUTO_BLOCK=true`. A
  heuristic block is an automatic outage for everyone sharing that
  address, and on mobile networks that is a lot of people.
- Blocks always expire. A permanent block is a firewall rule an operator
  makes deliberately outside the application; letting the dashboard mint
  one invites a forgotten block that outlives everyone who remembers why.
- The request path reads a 30-second cached set rather than the table.
  Writes invalidate it eagerly, so an operator's block or unblock bites
  on the next request; only a block *lapsing on its own* can lag.
- A blocked request gets the standard error envelope with
  `code: "request_blocked"`. A bespoke body would be one more thing for a
  scanner to fingerprint.

### 7. Watching must never break serving

Every detector call site is wrapped in `try/except` that logs and
continues. A monitoring feature that can take the platform offline is a
worse availability risk than the scanners it watches for.

Cost is asserted, not assumed: `test_ordinary_browsing_adds_no_database_queries`
measures a clean request with the watcher off and on and requires the
same query count. A database write happens only when a rule fires.

### 8. Developer tools cannot be blocked — so the guard reports instead

**A web page cannot prevent DevTools from opening.** It cannot detect
them reliably either. Everything on offer is a heuristic:

| Technique | Why it does not hold |
|---|---|
| `keydown` on F12 / Ctrl+Shift+I | Devtools also open from the browser menu, the command palette, a keyboard remap, or `--auto-open-devtools-for-tabs`. |
| Window-size delta (outer vs inner) | Fires on an undocked window; misses a docked one; false-positives on zoom, on-screen keyboards and browser translation bars. |
| `debugger`-statement timing | Only fires when devtools are open *and* the debugger is enabled; visibly janks the page; trivially defeated by turning breakpoints off. |
| Disabling the context menu | Copy/paste and "open in new tab" break for real users; `view-source:` and `curl` are unaffected. |

And none of it applies at all to the audience that matters: an attacker
reads the JavaScript with `curl`, from the network tab of a browser with
scripts disabled, or from the published source map. **Anything shipped to
the browser is public.** The guard is a speed bump against casual
poking, and — the part with real value — a *signal source*.

So the guard has three modes, set by one environment variable
(`SECURITY_CLIENT_GUARD_MODE`, served to the browser by
`GET /api/v1/security/client-policy/`):

- `off` — nothing ships.
- `detect` (**default**) — observe and report; never interfere.
- `deter` — additionally intercept F12 / Ctrl+Shift+I / Ctrl+Shift+J /
  Ctrl+U / right-click.

Signed-in visitors are exempt by default
(`SECURITY_GUARD_EXEMPT_AUTHENTICATED`), which is the requested "only
logged-in users can open devtools" behaviour expressed the honest way
round: *anonymous* visitors meet the speed bump, signed-in ones do not.

An unrecognised mode falls back to `off`, not to the strictest setting: a
typo in an env var must never turn a user-hostile mode on by accident.

### 9. Client-reported signals are advisory and cannot be forged upward

The one public write endpoint, `POST /api/v1/security/client-signals/`:

- accepts **only** the four client-reportable kinds. A browser posting
  `scanner_agent` gets a 400. Without that rule any visitor could have
  the platform auto-block whatever address they named.
- takes the source address **from the connection**. There is no `ip`
  field, and `StrictSerializer` rejects the request outright if one is
  supplied rather than ignoring it.
- is rate-limited (`SECURITY_SIGNAL_RATE`, default `30/min`) — it is
  anonymous by necessity, so throttling is not optional.
- answers `{"recorded": true|false}` and nothing else. Telling a probe
  its own score would turn the dashboard into a tuning aid.
- carries the lowest weights in the table (1–8). Ten devtools reports —
  the loudest a browser can be — still rank below one real probe, and
  `test_client_signals_alone_cannot_reach_a_blocking_band` enforces it.

### 10. Crawler policy: allow the crawlers that should crawl

Search engines and social unfurlers are matched **before** the automation
list and scored zero. A recipe platform wants to be indexed. `robots.txt`
states the intent; it is a request, not a control, and the enforcement
side is this app.

`curl`, `requests`, `scrapy` and friends score 12 — noteworthy on a
browser-facing page, entirely normal against an API, so low enough that
it takes sustained repetition to matter.

## Consequences

**Gained**

- Probing is visible, aggregated per source, and banded — with filters
  by kind, severity, band, review state, address and free text.
- Every switch is an environment variable with a safe default; nothing
  new is enforced on an existing deployment until someone opts in.
- 81 tests, including the negative cases that keep real learners and
  search engines out of the log.

**Accepted costs**

- **The devtools guard is not a control and is documented as one.** No
  claim anywhere in the product says otherwise.
- Sliding-window detection (404 sweeps, floods, auth bursts) counts in
  the cache. With `LocMemCache` each worker counts separately, so
  thresholds are effectively per-worker in development. Production
  already uses Redis, where the count is shared.
- An IP is not a person. Shared addresses, carrier NAT and corporate
  egress all appear as one profile; that is exactly why auto-blocking is
  off by default and blocks expire.
- `X-Forwarded-For`'s first entry is trusted, matching the existing
  `client_ip` helper. Behind a misconfigured proxy that value is
  attacker-controlled — the same assumption the rest of the platform
  already makes, not a new one.

## Alternatives rejected

**A WAF / Cloudflare / fail2ban instead of application code.** Better at
blocking, and it should still be used in production — but it cannot see
`is_staff`, cannot join a signal to a KawaiiBake account, and puts the
dashboard outside the product. This app is the layer that knows the
application; it is complementary to an edge WAF, not a replacement.

**Scoring on every request.** Would give a smoother picture at the cost
of a write per request. Rejected: the watcher must be free for the 99.9%
of traffic that is a learner reading a recipe.

**Storing only events and computing bands on read.** Honest, no drift —
and unusable, since filtering by band would mean aggregating the whole
table per page load. The compromise is the stored cache plus
`recount_threats` to prove it.

**Obfuscating or encrypting the frontend bundle.** Raises the effort to
read the code slightly, breaks source maps and debugging permanently, and
protects nothing that is not already served to every visitor.

**Auto-blocking on the first honeypot hit.** One `/.env` request from a
shared university address would lock out a classroom. `high` is the
signal; blocking stays a decision.

## Known gaps

- **The Next.js origin needs its own trap coverage.** Requests to
  `https://kawaiibake.example/.env` never reach Django. The frontend
  middleware forwards those hits to the ingest endpoint; forwarding a
  *visitor's* address requires `SECURITY_INGEST_SECRET` to be set on both
  sides, and without it the event is recorded against the frontend
  server's address instead of being lost.
- **No notification on `critical`.** The notifications app is a
  per-recipient sink and has no "all staff" event type; wiring one is a
  separate decision. Today an operator has to look at the dashboard.
- **No geo/ASN enrichment.** Would need a third-party database and a
  privacy decision; deliberately out of scope.
