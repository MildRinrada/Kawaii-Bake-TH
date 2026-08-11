# KawaiiBake  Coding Guidelines

## 1. Style

- **PEP 8** enforced via `ruff` (config in `pyproject.toml`).
- `snake_case` for functions, variables, modules; `PascalCase` for classes;
  `UPPER_SNAKE_CASE` for constants.
- Maximum line length: 100.
- **Absolute imports only**: `from apps.recipes.services import ...`
   never relative (`from ..services import ...`).

## 2. Typing & Documentation

- Type hints on every function signature.
- Docstrings (Google style) on every public function, class, and module.

```python
def enroll_user(*, user_id: int, course_id: int) -> "Enrollment":
    """Enroll a user into a course.

    Args:
        user_id: ID of the enrolling user.
        course_id: ID of the target course.

    Returns:
        The created Enrollment.

    Raises:
        CourseFullError: If the course has reached capacity.
    """
```

- Services and selectors take **keyword-only arguments** (`*`) for clarity.

## 3. Layer Rules (non-negotiable)

1. **Views are thin.** Parse request → check permission → call service/selector → render.
2. **No ORM queries outside `repositories/` / `selectors/`.**
3. **No business logic in models, views, templates, or signals.**
4. **Services orchestrate; they do not render** (no `HttpResponse`, no `request`).
5. **Constants**  no magic strings/numbers; use `constants.py` enums.
6. **Exceptions**  raise domain exceptions from `exceptions.py`; views translate
   them into user-facing messages.
7. Cross-app access goes through the other app's `services/` / `selectors/`
   public API (what their `__init__.py` re-exports)  never inner modules.
8. **Vendor SDKs** appear only in `infrastructure/` and `ai/providers/`.

## 3b. Package Rule

- Growing layers are **packages of small domain modules**, never single files:
  `services/recipe_service.py`, not a 2,000-line `services.py`.
- **Maximum ~300 lines per file.** Crossing it is the signal to split by domain.
- Each layer package's `__init__.py` re-exports the public API; everything else
  is private to the app.

## 4. Functions

- Small, single-purpose, reusable.
- No duplicated logic  extract to `utils.py`, `apps/common/`, or `apps/core/`.
- Prefer pure functions in `utils.py` (no DB, no side effects).

## 5. API Layer (DRF)

Django is API-only. Views live in `api/views/`, serializers in
`api/serializers/`, routes in `api/urls/`.

**Division of labour:** the serializer validates the *message* (presence, type,
length, choice membership); `validators/` validates the *domain* (uniqueness,
reserved handles, age limits, image bytes). Domain rules run inside services so
they hold for every caller, not only HTTP.

**The view calls the service  never the serializer.** A serializer's job ends
at `validated_data`.

**Banned**, because each executes ORM inside the HTTP layer and would dissolve
rule 3.2:

- `ModelSerializer` for writes
- `serializer.save()` / `.create()` / `.update()`
- `queryset` or `get_object()` on a view
- `UniqueValidator`, `PrimaryKeyRelatedField(queryset=…)`, `SlugRelatedField`
- traversing an un-prefetched relation in an output serializer

Use plain `APIView`. Reach for `GenericAPIView` only for pagination, and
paginate a **selector's** queryset.

Read and write serializers are separate classes. A write serializer must not
declare identity or permission fields  that is the mass-assignment guard.

Unauthenticated POST endpoints must inherit `CsrfProtectedAPIView`: DRF
`csrf_exempt`s every `APIView`, and `SessionAuthentication` enforces CSRF only
for already-authenticated requests.

Privacy is applied in the **selector**, by returning a redacted DTO  never by
conditional logic in `to_representation`, which fails open.

### Templates

The only templates in the project are email bodies, in
`apps/<app>/templates/<app>/emails/`. They render without a request (often from
a Celery worker), so context processors do not apply  pass every value
explicitly in `TemplatedEmail.context`.

## 6. Tests

- Every service, selector, repository, and view gets tests in the app's `tests/`.
- Cross-app flows → `tests/integration/`.
- Use factories (`tests/factories.py`), not fixtures dumps.
- Test naming: `test_<unit>_<scenario>_<expected>`.

## 7. Git

- Branches: `feature/<app>-<short-description>`, `fix/...`, `chore/...`.
- Conventional commits: `feat(recipes): ...`, `fix(quizzes): ...`.
- No secrets in the repo  environment variables only (`.env`, documented in `.env.example`).

## 8. Migrations

- One logical change per migration.
- Never edit an applied migration; create a new one.
- Data migrations get descriptive names: `0005_backfill_recipe_slugs.py`.
