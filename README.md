# KawaiiBake

KawaiiBake is a Thai-first bakery learning platform for learning baking through recipes, courses, quizzes, an AI baking assistant, and community features.

The project consists of a Django API-only backend and a Next.js frontend. Django serves JSON through `/api/v1/` and does not render application pages. The entire user interface is implemented in `frontend/`.

## Features

### Recipes

* Recipes with ingredients, preparation steps, timings, and nutrition information
* Baking mode with step-by-step guidance
* Built-in timers
* Private recipe notes
* Ingredient substitutions
* Favourites
* Reviews and star ratings

### Courses

* Instructor-owned courses
* Public course syllabus
* Enrolment-gated lessons
* Free preview lessons
* Quizzes using a reusable question bank
* Persistent learning progress
* Course completion certificates
* Anonymous certificate verification links

### AI Assistant

KawaiiBake includes a Thai-first AI baking assistant.

The assistant can be used independently or anchored to the recipe or lesson currently being viewed, allowing users to ask questions in the context of what they are learning.

The AI layer uses a pluggable provider architecture. An offline mock provider is available by default for local development.

### Community

* Baking gallery for sharing completed recipes
* Question board for asking baking-related questions
* Answers and accepted answers

### Progress and Rewards

User progress is derived from actual activity on the platform.

* XP and levels
* Learning and activity streaks
* Badges
* Rewards ledger
* In-app notifications
* Per-event notification preferences

### Administration

The platform includes a back-office for managing:

* Recipes
* Courses
* Users
* Reviews
* Certificates
* Announcements
* Audience-targeted notification campaigns
* Notification delivery analytics

## Architecture

KawaiiBake uses a domain-oriented architecture with Django serving as an API-only backend.

```text
KawaiiBake
├── config/             # Django settings, URLs, WSGI, ASGI, Celery
├── apps/               # Feature applications, organized by domain
├── ai/                 # Framework-free AI provider package
├── infrastructure/     # Cache, email, storage, queue, search, logging
├── frontend/           # Next.js application
├── media/              # User uploads, not committed to Git
├── docs/               # Documentation and architecture decision records
├── tests/              # Cross-application integration tests
├── scripts/            # Operational scripts
├── docker/             # Dockerfiles and Docker Compose files
└── requirements/       # Layered Python dependencies
```

The backend is responsible for authentication, business logic, data access, validation, and API responses.

The frontend is responsible for the application interface and communicates with the backend through the REST API.

## Technology Stack

| Layer          | Technology                                        |
| -------------- | ------------------------------------------------- |
| Backend        | Python 3.12+, Django 5, Django REST Framework     |
| Database       | PostgreSQL, SQLite for local development          |
| Cache / Broker | Redis                                             |
| Workers        | Celery                                            |
| Frontend       | Next.js 16, TypeScript, React 19, Tailwind CSS v4 |
| AI             | Pluggable provider package                        |
| API Schema     | OpenAPI                                           |
| Deployment     | Docker                                            |

## Getting Started

### Backend

Create a Python virtual environment and install the development dependencies.

```bash
python -m venv .venv

# Windows
.venv/Scripts/pip install -r requirements/development.txt

# Unix
.venv/bin/pip install -r requirements/development.txt
```

Create the environment file:

```bash
cp .env.example .env
```

The default development configuration works without PostgreSQL or Redis.

Run database migrations:

```bash
.venv/Scripts/python manage.py migrate
```

Create an administrator account:

```bash
.venv/Scripts/python manage.py createsuperuser
```

Start the Django development server:

```bash
.venv/Scripts/python manage.py runserver
```

For Unix environments, use:

```bash
.venv/bin/python manage.py runserver
```

Development defaults include:

* SQLite database
* Console email backend
* Eager Celery tasks

To use PostgreSQL instead of SQLite, set:

```env
DB_ENGINE=postgres
```

### Backend URLs

| Service           | URL                               |
| ----------------- | --------------------------------- |
| API               | `http://localhost:8000/api/v1/`   |
| API documentation | `http://localhost:8000/api/docs/` |
| Django admin      | `http://localhost:8000/admin/`    |

The Django admin is restricted to staff users.

### Frontend

Install the frontend dependencies:

```bash
cd frontend
npm install
```

Create the local environment file:

```bash
cp .env.example .env.local
```

The default configuration points the frontend to:

```text
http://localhost:8000/api/v1
```

Start the Next.js development server:

```bash
npm run dev
```

The application will be available at:

```text
http://localhost:3000
```

The frontend uses session cookies when communicating with Django. Make sure the backend `CORS_ALLOWED_ORIGINS` includes the origin where the frontend is running.

The default configuration includes:

```text
http://localhost:3000
```

## Google Sign-In

Google Sign-In is optional.

Create an OAuth 2.0 Web application client in Google Cloud and configure the same client ID in both the backend and frontend.

Backend:

```env
GOOGLE_OAUTH_CLIENT_ID=your-client-id
```

Frontend:

```env
NEXT_PUBLIC_GOOGLE_CLIENT_ID=your-client-id
```

A client secret is not required by the application.

If the client ID is not configured, Google Sign-In is disabled. The frontend does not render the sign-in button and the corresponding backend endpoint returns `503`.

## Testing

### Backend tests

Run the complete backend test suite:

```bash
.venv/Scripts/python -m pytest
```

Run linting:

```bash
.venv/Scripts/python -m ruff check .
```

### Frontend checks

```bash
cd frontend

npm run typecheck
npm run lint
```

### Browser E2E tests

The E2E scripts use a real browser against a running frontend and backend.

Start both servers first, then run:

```bash
node e2e-recipe-list.mjs
```

The E2E and probe scripts are located in:

```text
frontend/
```

Each script reads `BASE_URL`.

The default value is:

```text
http://localhost:3000
```

## API Type Generation

The frontend TypeScript types are generated from the backend OpenAPI schema.

Generate the schema:

```bash
.venv/Scripts/python manage.py spectacular --file frontend/schema.yml
```

Generate the frontend API types:

```bash
cd frontend
npm run generate:api-types
```

This keeps the frontend API types synchronized with the backend contract. Changes to backend response fields can therefore be detected during frontend type checking instead of appearing only as runtime errors.

## Development Principles

KawaiiBake follows several architectural principles:

* Django is API-only and does not render application pages.
* Frontend and backend communicate through an explicit API contract.
* Domain logic is kept within the relevant application.
* Infrastructure concerns are isolated from domain logic.
* AI providers are replaceable through a dedicated provider interface.
* OpenAPI is the source for generated frontend API types.
* Development should work with minimal external services where possible.
* User progress should be derived from actual application activity rather than duplicated counters.
* Notification records should remain independent from the domains that produce them.

## Documentation

Additional documentation is available in the `docs/` directory.

* [Architecture](docs/Architecture.md) - application architecture, layering, credential boundaries, and DRF conventions
* [API](docs/API.md) - API endpoints, authentication flow, error responses, and frontend integration
* [Database](docs/Database.md) - database structure and intentionally omitted tables
* [Folder Structure](docs/FolderStructure.md) - project organization
* [Coding Guidelines](docs/CodingGuidelines.md) - development conventions
* [Decision Records](docs/adr/README.md) - architectural decisions and their rationale

## License

TBD
