# 0002 — Service / Repository / Selector Layers

- **Status:** Accepted
- **Date:** 2026-08-06

## Context

Business logic in views or models makes code untestable and unreusable, and
scattered ORM queries make performance work (indexing, caching, N+1 fixes)
impossible to localize.

## Decision

- **Views** stay thin: parse request → permission check → call service/selector → render.
- **Services** own business logic and write orchestration.
- **Repositories** own write-side / complex DB access.
- **Selectors** own read-side reusable queries.
- Each layer is a *package* of small domain modules (~300 lines max per file),
  e.g. `services/recipe_service.py`, `selectors/recipe_selector.py`.

## Consequences

- The future REST API and mobile app reuse services unchanged.
- Read-path optimization (caching, `select_related`) has one home: selectors.
- More files per feature — mitigated by a strictly uniform layout.
