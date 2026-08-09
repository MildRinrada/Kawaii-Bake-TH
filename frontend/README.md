# KawaiiBake Frontend

Next.js (App Router) + TypeScript + Tailwind CSS v4. **Structure-first**:
the visual design direction arrives in the next phase — everything here
is architecture, semantic tokens and neutral primitives, built to be
restyled without restructuring.

## Run

```bash
npm install
cp .env.example .env.local   # optional — defaults target localhost:8000
npm run dev                  # http://localhost:3000 (backend on :8000)
```

## Scripts

| Script | Purpose |
|---|---|
| `npm run dev` | Dev server (Turbopack) |
| `npm run build` | Production build |
| `npm run lint` | ESLint (flat config) |
| `npm run typecheck` | `tsc --noEmit` |
| `npm run generate:api-types` | Regenerate `src/lib/api/types.ts` from `schema.yml` (`manage.py spectacular --file frontend/schema.yml` first) |

## Architecture

- `src/styles/tokens.css` — **the design seam.** Semantic placeholder
  tokens (surface/fg/accent/status, radius, shadows, fonts). The visual
  phase edits this file; components never reference raw colors.
- `src/lib/api/` — one fetch client (session cookies + CSRF + the
  backend error contract), generated OpenAPI types, model aliases.
- `src/lib/auth/` — `AuthProvider` mirrors the Django session
  (`/users/profile/`), `RequireAuth` guards protected routes client-side
  (the session cookie is httpOnly on the API origin).
- `src/lib/forms/` — submit-state hook mapping `error.details` onto
  form fields.
- `src/components/ui/` — 14 neutral structural primitives.
- `src/components/layout/` — `AppShell`, `PageHeader`, `SectionShell`
  (the honest placeholder shells render until pages are designed).
- `src/app/` — `(auth)` group (login/register, wired) and `(main)` group
  (all product routes as structural shells; recipes list + profile are
  wired end-to-end to prove the data path).

## Deliberately undecided (waiting for the design phase)

Brand palette, typography personality, radius/shadow language, dark
mode, navigation pattern, card/list appearance, illustrations, motion.
All of it lands in `tokens.css` + per-component variant maps.
