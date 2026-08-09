# 0008 — Cross-App Model References

- **Status:** Accepted
- **Date:** 2026-08-07

## Context

The architecture says a feature app may only reach another through its public
service/selector API, never its models. Phase 2 hit the first case the rule does
not cleanly cover: a recipe genuinely *has* categories, and there is no way to
express that relationally without naming `RecipeCategory`.

## Decision

Draw the line at **imports, not references**:

> A lazy string model reference is a *schema declaration*. A Python import is a
> *code dependency*. Only the second is coupling.

`ManyToManyField("recipe_categories.RecipeCategory")` is resolved by Django's app
registry at check time and creates **no import edge**. The project already
depends on exactly this mechanism: `settings.AUTH_USER_MODEL` is a string
reference, and `Profile.user` pointing at another app's model has never been
considered a violation.

### Permitted

1. A lazy string M2M/FK to another app's model. **`recipes` owns the
   many-to-many**, because `recipes` is the dependent side — this keeps
   `recipe_categories` a leaf that can ship on its own.
2. Reads through the other app's selector package:
   - `category_selector.resolve_slugs(slugs=…) -> dict[str, int]`
   - `category_selector.ref_queryset()` — the narrowed queryset to prefetch with
   - `category_selector.list_categories()`
3. Writing the join table (`recipe.categories.set(ids)`). That writes only the
   table `recipes` owns; it never writes a `RecipeCategory` row.

### Not permitted

- `from apps.recipe_categories.models import RecipeCategory` inside `apps/recipes`
- importing another app's `repositories` (write-side internals)
- `RecipeCategory.objects.…` in a `recipes` selector or service
- `recipe_categories` declaring a relation to `recipes` — that would invert the
  dependency and make the taxonomy unshippable alone

### Errors belong to the caller

`resolve_slugs` returns what it found and nothing more. `recipes` diffs the
result and raises its **own** `InvalidCategoryError`. A callee must never raise
the caller's exception.

### `ref_queryset()` is the load-bearing detail

Without it, the recipes selector would write
`Prefetch("categories", queryset=RecipeCategory.objects.only(...))` — a real
import of another app's model into another app's ORM code. With it, `recipes`
never names the class, and the day categories gain a visibility rule, one
function fixes every consumer.

## Consequences

- The relationship is expressed properly, with a real join table and real
  referential integrity.
- `apps.recipe_categories` is listed **before** `apps.recipes` in
  `INSTALLED_APPS` to document the direction.
- This needs an `import-linter` contract to stay true: `apps.recipes` must not
  import `apps.recipe_categories.models` or `.repositories`. `Architecture.md`
  has asked for these contracts since Phase 1; this is the moment they earn
  their keep.
- The `BakingCategory` enum in `apps/users/constants.py` duplicates this
  taxonomy. Migration `recipe_categories.0002` seeds identical slugs, which is
  what makes the eventual `Profile.favorite_categories` JSON → M2M backfill an
  exact match rather than manual reconciliation.

## Related: untested production search

Recorded here because it is the other boundary decision made in Phase 2.
`infrastructure/search/postgres_search.py` uses `pg_trgm` and **is not executed
by any test** — the suite runs on SQLite, and `SearchVector`/`TrigramWordSimilarity`
cannot even be compiled without the PostgreSQL backend, so not even a SQL-string
assertion is possible.

The default `SimpleSearchBackend` is portable and fully covered. Enabling the
PostgreSQL backend in production means running code the suite has never
executed. The honest fix is a CI job against a real `postgres:16` service
container with a `pytest.mark.postgres` marker; until that exists, this
limitation is accepted in writing rather than hidden by the adapter.

Note also *why* the PostgreSQL backend is trigram-first rather than
`tsvector`-first: `to_tsvector` tokenises on whitespace, and Thai is written
without inter-word spaces, so a whole Thai phrase becomes a single token and
searching for a word inside it matches nothing. Trigram similarity needs no
tokenisation and works on Thai.
