# KawaiiBake 🧁

A Thai-first bakery learning platform: recipes you can actually cook
from, courses with lessons and quizzes, certificates when you finish, an
AI baking assistant, and a community to ask when the dough will not
rise.

**Django is API-only.** It serves JSON at `/api/v1/` and renders no
pages; the entire interface is a Next.js app in [`frontend/`](frontend/).

## What it does

**Cook** — recipes with ingredients, steps, timings and nutrition; a
baking mode that walks one step at a time with timers, private notes and
ingredient substitutions; favourites, reviews and star ratings.

**Learn** — instructor-owned courses with a public syllabus and
enrolment-gated lessons, free preview lessons, quizzes drawn from a
reusable question bank, progress that survives un-completing, and a
certificate with an anonymous verification link when a course is done.

**Ask** — a Thai-first AI assistant that can be anchored to the recipe or
lesson you are looking at, plus a community: a gallery of "I baked this"
posts and a question board with accepted answers.

**Keep going** — XP, levels and streaks derived from what you actually
did (no separate score to keep in sync), badges, a rewards ledger, and an
in-app notification centre with per-event preferences.

**Run the place** — a back-office for recipes, courses, users, reviews,
certificates and announcements, with audience-targeted notification
campaigns and honest delivery analytics.

## Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12+, Django 5, Django REST Framework |
| Database | PostgreSQL (SQLite for local development) |
| Cache / broker | Redis (optional locally) |
| Workers | Celery |
| Frontend | Next.js 16, TypeScript, React 19, Tailwind CSS v4 |
| AI | Pluggable provider package (`ai/`) — offline mock by default |
| Deploy | Docker |

## Quick start

### Backend

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements/development.txt   # Unix: .venv/bin/pip

cp .env.example .env          # optional — the defaults run out of the box
.venv/Scripts/python manage.py migrate
.venv/Scripts/python manage.py createsuperuser
.venv/Scripts/python manage.py runserver
```

Development defaults to SQLite, console email and eager Celery tasks, so
neither PostgreSQL nor Redis is required to run locally. Set
`DB_ENGINE=postgres` to use PostgreSQL.

- API root: `http://localhost:8000/api/v1/`
- Interactive docs: `http://localhost:8000/api/docs/`
- Django admin (staff only): `http://localhost:8000/admin/`

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local    # points at http://localhost:8000/api/v1
npm run dev
```

- App: `http://localhost:3000`

The frontend talks to Django with session cookies, so the backend's
`CORS_ALLOWED_ORIGINS` must include the origin you serve it from (the
default covers `http://localhost:3000`).

### Optional: Google sign-in

Create an OAuth 2.0 **Web application** client in the Google Cloud
console and put the same client id in both halves —
`GOOGLE_OAUTH_CLIENT_ID` (backend) and `NEXT_PUBLIC_GOOGLE_CLIENT_ID`
(frontend). No client secret is involved. Left empty, the feature is
simply absent: no button is rendered and the endpoint answers 503.

## Tests

```bash
.venv/Scripts/python -m pytest        # backend suite
.venv/Scripts/python -m ruff check .  # lint

cd frontend
npm run typecheck && npm run lint
node e2e-recipe-list.mjs              # browser E2E — needs both servers running
```

The `e2e-*.mjs` and `probe-*.mjs` scripts in `frontend/` drive a real
browser against a real backend; each reads `BASE_URL` (default
`http://localhost:3000`).

## API types for the frontend

```bash
.venv/Scripts/python manage.py spectacular --file frontend/schema.yml
cd frontend && npm run generate:api-types
```

TypeScript types are generated from the OpenAPI schema, so a backend
field change becomes a frontend compile error rather than a runtime
surprise.

## Project layout

```
config/         # Settings, root URLs, WSGI/ASGI, Celery
apps/           # Feature apps — one per domain
ai/             # Framework-free AI package
infrastructure/ # Adapters for cache, email, storage, queue, search, logging
frontend/       # Next.js app (see frontend/README.md)
media/          # User uploads (not committed)
docs/           # Documentation + decision records
tests/          # Cross-app integration tests
scripts/        # Operational scripts
docker/         # Dockerfiles & compose files
requirements/   # Layered dependency files
```

## Documentation

- [Architecture](docs/Architecture.md) — layering, the credential seam, DRF rules
- [API](docs/API.md) — endpoints, auth flow, error contract, frontend integration
- [Database](docs/Database.md) — the tables and what was deliberately omitted
- [Folder Structure](docs/FolderStructure.md)
- [Coding Guidelines](docs/CodingGuidelines.md)
- [Decision Records](docs/adr/README.md) — why things are the way they are

## License

TBD
