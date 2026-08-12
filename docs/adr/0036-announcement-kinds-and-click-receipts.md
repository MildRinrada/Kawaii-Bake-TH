# ADR 0036 — Announcement kinds are a closed set, and clicks are a floor

- **Status:** accepted
- **Date:** 2026-08-12
- **Phase:** Notification polish
- **Amends:** [0030](0030-notification-campaigns.md) — the composer's
  `icon` field and the free-slug kind catalog

## Context

ADR 0030 shipped campaigns with two deliberately loose pieces: `kind`
was "a frontend catalog over a validated backend slug", and each
campaign carried an `icon` — an emoji the composer asked staff to pick.

Both turned out wrong in the same way. The design review of the
notification centre replaced per-campaign emoji with one glyph system,
so the emoji stopped being rendered at all; and because every
announcement then drew the same lavender pin, "ระบบจะปิดปรับปรุงคืนนี้"
and "มีคอร์สใหม่มาแล้ว" were indistinguishable in a list. Meanwhile the
analytics panel could report only delivered and read, and said so — the
honest position, but the one question staff actually ask about a link is
whether anyone followed it.

## Decisions

### 1. Six kinds, closed, each with one drawing

`AnnouncementKind`: `general`, `feature`, `event`, `maintenance`,
`policy`, `alert`. Enforced by the write serializers (an unknown kind is
a 400) and mirrored once in the frontend's `ANNOUNCEMENT_KINDS`, which
maps each to a glyph and a colour pair.

The sender picks a *category*; the design system picks the picture. That
is the inversion the emoji field had backwards — and it is why the
picker in the composer shows the real glyph and colour rather than a
label, so nobody has to send one to find out what it looks like.

Free slugs were justified in 0030 as "new types are a catalog entry, not
a migration". True, and the cost was a value the client could not draw.
Six categories cover what a bakery platform announces; a seventh is a
constant, a colour and a line in this ADR.

### 2. The `icon` column is gone, and the kind is copied into the snapshot

`Notification.icon`, `NotificationCampaign.icon` and
`NotificationTemplate.icon` are dropped. Nothing had rendered them since
the notification rework, so the migration loses decoration, not
information; the data migration maps every pre-existing free-form kind
onto `general` and backfills delivered announcements from their campaign
so an inbox looks the same after the deploy as before it.

`Notification.kind` is a **copy**, not a join through the campaign FK —
the same rule every other field on that row follows (ADR 0016): the row
is what the recipient was told. Amending a sent campaign still rewrites
delivered snapshots, because that is an explicit, all-recipients-at-once
operation with its own endpoint.

### 3. A click is what the client reports, and the panel says so

`POST /me/notifications/{id}/click/` stamps `clicked_at` once and
`read_at` with it — you cannot open what a notification points at without
having read it, and folding them saves the client a round trip on the
one action it takes while navigating away.

There is no redirect endpoint. Bouncing every notification link through
the API would turn in-app navigation into a server round trip, break
`next/link` prefetching, and produce URLs that are useless when copied.
The cost of not doing it is that the count is a **floor**: a middle-click
into a new tab, a copied link or a blocked script is a real click nobody
records. Both the admin panel and `docs/API.md` state that in words
rather than presenting the number as a measurement.

A click on a row with no link is a 409 `not_clickable`, not a silent
200 — accepting it would put clicks in the analytics that no recipient
could have made.

### 4. Rates are over delivered, never over recipients

`read_rate` and `click_rate` both divide by `delivered`. Recipients is
what the audience resolved to; delivered is how many snapshots exist.
Dividing by recipients would quietly flatter a send whose rows were
dropped by an opt-out.

## Consequences

- One migration: three columns dropped, two added
  (`Notification.kind`, `Notification.clicked_at`), two altered to
  choices, plus the data pass described above.
- The composer's 26-entry catalog with categories collapses to six cards.
  `kinds.ts` keeps the audience and variable catalogs unchanged.
- Staff can now see, per campaign, how many of the people who *read* an
  announcement went on to follow it — the "อ่านแต่ไม่กด" figure that
  tells you the headline worked and the link did not.

## Alternatives considered

**A redirect endpoint (`GET /n/{id}/go`).** Measures more (it catches
middle-clicks), and costs client-side navigation, prefetching and
shareable URLs. Rejected for an in-app-only notification system where
every link is a local path.

**Keeping `icon` as an optional override.** One escape hatch is all it
takes for the set to stop being closed, and the first override would be
the first announcement the reader's row cannot style consistently.
