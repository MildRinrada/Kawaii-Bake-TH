# ADR 0030 — Notification campaigns, templates and audiences

- **Status:** accepted (kind/icon amended by [0036](0036-announcement-kinds-and-click-receipts.md))
- **Date:** 2026-08-11
- **Phase:** back-office completion, part four

## Context

The staff notification surface was a single broadcast-to-everyone form
plus a delivery log. Operators wanted a real composer: typed
notifications with an icon, targeted audiences with a recipient count
up front, scheduling, reusable templates, and honest analytics — while
`/settings` remains strictly the *user's* preference page. The two must
never blur.

## Decisions

### 1. A campaign is a first-class record; delivery stays snapshots

`NotificationCampaign` stores what staff composed (kind, icon, title,
body, CTA, link, audience, lifecycle). Sending still produces the same
per-recipient `Notification` snapshots every machine event produces —
event type `announcement`, honoring the same opt-out — plus a nullable
`campaign` backreference used only for aggregation. The ADR 0016
"no FK to content" rule is amended precisely: the recipient stays the
only cross-app FK, and any intra-app FK must be `SET_NULL` so nothing
can cascade a recipient's history away (the model test now enforces
exactly that).

### 2. Audiences are a closed document, resolved through cross-app selectors

`{"kind": …, …params}` with nine kinds (all / active / new_users /
course_enrolled / course_completed / recipe_creators /
community_creators / skill_level / specific_users). The validator
closes kinds, params and ranges; resolution maps each kind to one
public selector (`user_selector`, `enrollment_selector`,
`recipe_selector.published_author_ids`, `gallery_selector.author_ids`) —
ids only, active accounts only, no other app ever queries the user
table. `estimate/` runs the *same* resolve-then-drop-opt-outs pipeline
a send runs, so the number the composer shows is the number a send
produces.

### 3. Variables must be resolvable or the send refuses

`{{user_name}}` resolves everywhere (public display name);
`{{course_name}}` only for course-scoped audiences. Drafts may hold
anything (the composer offers sample-only variables for preview), but
send and schedule reject unresolvable variables with a 400 — delivery
never ships a literal `{{like_count}}` to a real inbox. Rendering
happens per recipient at send time; the snapshot stores resolved text.

### 4. Sent is immutable; scheduling is honest about its dispatcher

Draft and scheduled campaigns are editable; sent ones are evidence — no
edit, no delete, no resend (409 `campaign_state`; duplicate instead).
Scheduled sends fire via `CELERY_BEAT_SCHEDULE` (a one-minute scan) or
`manage.py dispatch_campaigns` for cron setups; a deployment running
neither shows due campaigns flagged "ถึงกำหนดแล้ว" in the hub with a
manual send button, and the composer says so. Cancel moves scheduled →
canceled, never deletes.

### 5. Analytics report receipts, not wishes

In-app only: `delivered` = snapshots created, `read` = `read_at`
stamped, and the read rate is their quotient. There is no click
tracking, so no CTR is shown — the UI states this instead of inventing
one. Campaign snapshots carry the composer's `icon` and `cta_text`
(two new nullable-blank fields on `Notification`), and the user-facing
notification center renders them — emoji glyph, CTA link — falling back
to the per-event icon for machine events.

### 6. The page split

`/admin/notifications` is the hub (stats, tabbed campaign list,
templates); `/admin/notifications/compose` is the composer;
`/admin/notifications/log` is the moved per-recipient delivery log.
Templates (`NotificationTemplate`) are admin-side configuration with
archive semantics; campaigns copy from them, never reference them.

## Consequences

- The kind catalog is frontend data over a validated backend slug — new
  notification types are a catalog entry, not a migration.
- `active` audiences are as honest as `last_login` is: an account that
  never re-authenticates ages out of the window.
- The legacy `broadcast/` endpoint remains for compatibility; the hub's
  "ส่งประกาศ" flows through the campaign composer.
- E2E pins the loop: stats → compose (estimate resolves) → draft → send
  with confirmed estimate → sent row with analytics → template round
  trip → the moved log — zero unexpected 4xx.

## Amendment — 2026-08-11: sent campaigns are amendable and retractable

Operator decision superseding §"sent is immutable": notifications are
in-app rows, so un-sending and amending are *real*, and pretending
otherwise only forced workarounds.

- **Amend** — `PATCH` on a sent campaign accepts content fields only
  (kind/icon/title/body/CTA/link) and re-renders every delivered
  snapshot in the same transaction, per recipient, variables included —
  an inbox always shows the amended text, never a mix. The audience and
  schedule remain history: touching them is still a 409.
- **Retract** — `DELETE` on a sent campaign removes its delivered
  snapshots from every recipient's inbox together with the campaign
  row, inside one transaction. Scheduled campaigns must still be
  canceled before deletion. Read receipts of retracted deliveries are
  gone with them — deletion means deletion.
- Send-twice remains a 409; duplicating is still how staff re-run one.
- The composer opens sent campaigns in a content-only mode
  ("บันทึกและอัปเดตผู้รับ"), and the hub's sent-row menu gains
  แก้ไขเนื้อหา / ลบและเรียกคืนจากผู้รับ, both confirmed with the real
  recipient count. E2E now runs the full loop send → amend → retract,
  leaving recipient inboxes net-zero.
