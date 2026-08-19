# ADR 0029 - The certificate template designer

- **Status:** accepted
- **Date:** 2026-08-11
- **Phase:** back-office completion, part three

## Context

Certificates printed one hardcoded layout. Operators wanted per-course
designs, edited visually - drag, resize, publish - not a form. That
needs somewhere to keep a design, and a shape for it that can never
become an injection vector.

## Decisions

### 1. A design is a validated JSON scene, never markup

`CertificateTemplate` (one row per course) stores a scene graph:
absolutely-positioned elements (`field`, `text`, `image`, `signature`,
`box`) over a fixed canvas. The backend validator closes every enum,
bounds every number, caps elements at 60 and signatures at **3**, and
length-caps every string; the frontend renders documents exclusively
through typed React styles. Dynamic fields are a closed key set
(recipient name, course, dates, certificate id, instructor, …) rendered
with sample data in the editor and filled with real data at issuance.

### 2. Draft and published are different columns, deliberately

Autosave (debounced `PUT …/templates/{slug}/`) writes `draft_design`
only. `POST …/publish/` copies draft → `published_design` and stamps
who/when - experimenting never touches production. `reset/` walks the
draft back to the published version (or the built-in default), and
`DELETE` drops the row so the course uses the default design again. The
default lives server-side (`template_service.DEFAULT_DESIGN`) so a
fresh course, "reset to default" and the seeded draft all agree.

### 3. The editor is history-per-gesture

The designer (three-pane: library+layers / canvas / properties) keeps
snapshot history where one pointer gesture - a whole drag, a whole
resize - is one undo step, and property edits commit individually.
Direct manipulation and the numeric inputs drive the same document, so
each immediately reflects the other. Grid snap (4px), canvas-center
guides, zoom (25–100% + fit), a clean full-screen preview with sample
recipients, and keyboard nudge/duplicate/delete/undo round out the
tool.

### 4. The issued registry moved, not merged

`/admin/certificates` is now the designer workspace; the issued-paper
registry and the public-token verification tool live unchanged at
`/admin/certificates/issued`. Templates are design; issued certificates
are evidence - one page must not be both.

## Consequences

- Published designs are stored and versioned per course; **rendering an
  issued certificate from its course's published template is a future
  phase** - issuance snapshots are text today, and this ADR does not
  change that.
- Image elements reference curated public assets or staff-entered URLs;
  uploads would need a media endpoint and are deliberately out of scope.
- E2E pins the loop: workspace → designer → add element → autosave →
  undo → autosave, plus the moved registry - with zero unexpected 4xx.

## Amendment - 2026-08-11

- **Field override.** A `field` element may carry a non-blank `text` -
  a staff override ("มอบโดย เชฟมิลด์") that replaces the automatic
  value on every certificate. Blank keeps the automatic behaviour. The
  backend validator now length-caps `text` on field elements exactly
  like free text (closing a previously unvalidated key), and the
  properties panel labels the element's state honestly (อัตโนมัติ vs
  กำหนดเอง). This is how a custom presenter/awarder name is set without
  breaking the closed field-key set.
- **Fit-zoom stability.** The stage reserves its scrollbar gutter and
  the fit-scale recomputes only on canvas-size changes with a small
  dead-band - previously the scrollbar and the scale fed each other and
  the certificate frame visibly vibrated while resizing the window.
