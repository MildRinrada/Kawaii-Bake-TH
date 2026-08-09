# 0005 — API-Only Backend with a Next.js Frontend

- **Status:** Accepted
- **Date:** 2026-08-07
- **Supersedes:** the server-rendered (MVT) assumption in ADR 0001–0004

## Context

The original architecture was Django MVT: Django templates, HTMX, Alpine.js and
Bootstrap, with per-app `templates/` and `static/` directories. The product
direction changed to a separated frontend: Next.js + TypeScript + React +
Tailwind owning the entire user interface.

Keeping both would mean two rendering paths, two sets of UI conventions, and
duplicated view logic.

## Decision

Django becomes **API-only**. It exposes JSON under `/api/v1/` and renders no
pages. Concretely:

- Each feature app gains an `api/` package: `api/views/`, `api/serializers/`,
  `api/urls/`.
- The `forms/` layer is removed, except `apps/users/forms/admin_forms.py` —
  a custom user model *requires* admin forms, or the admin stores plaintext
  passwords.
- Root `templates/` and `static/`, and all per-app template and static
  directories, are deleted — **except** `templates/<app>/emails/`.
- `TEMPLATES` stays configured with `APP_DIRS: True` and `DIRS: []`, and
  `staticfiles` stays installed. Django admin and email rendering both require
  them; removing either breaks `/admin/`.
- `LOGIN_REDIRECT_URL` and `LOGOUT_REDIRECT_URL` are dropped; `LOGIN_URL`
  becomes `admin:login`.
- `drf-spectacular` generates an OpenAPI schema so the frontend can generate
  TypeScript types.

## Consequences

- One rendering path, one set of UI conventions.
- The API is reusable by the planned mobile app with no additional work.
- Cross-origin concerns become real: CORS, CSRF and cookie `SameSite` must be
  configured deliberately (see ADR 0007).
- DRF's conveniences (`ModelSerializer`, `serializer.save()`, `queryset` on
  views) would run ORM inside the HTTP layer and are therefore banned; the ban
  is documented in `CodingGuidelines.md` and should be enforced with
  `import-linter`.
- Email bodies remain the one server-rendered surface, and they render without a
  request — so context processors never apply and values must be passed
  explicitly. This matters because emails are sent from Celery workers.
