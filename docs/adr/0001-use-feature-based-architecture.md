# 0001 — Use Feature-Based Architecture

- **Status:** Accepted
- **Date:** 2026-08-06

## Context

KawaiiBake will grow for years across many domains (recipes, courses, quizzes,
gamification, AI). A traditional layer-first Django layout (one giant `views.py`,
`models.py` per concern) concentrates change in shared files and scales poorly
with team size.

## Decision

Organize the project as vertical feature slices under `apps/`. Each app owns its
models, views, templates, static files, business logic, tasks, and tests.
Feature apps never import another feature app's internals; shared code lives
only in `apps/core`, `apps/common`, or `infrastructure/`.

## Consequences

- New features are new folders; merge conflicts stay rare.
- Any hot feature can later be extracted toward a microservice.
- Requires discipline (and lint enforcement) on cross-app imports.
