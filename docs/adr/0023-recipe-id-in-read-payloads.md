# ADR 0023 — Recipe read payloads carry the primary key

- **Status:** Accepted
- **Date:** 2026-08-09
- **Supersedes:** nothing
- **Superseded by:** nothing

## Context

Recipes are addressed by slug throughout the public API
(`/recipes/{slug}/`), and their read serializers deliberately omitted
the primary key.

Other apps, however, *write* by id. `GalleryPostCreateSerializer` takes
`recipe_id` — that FK is the backend's own mechanism for "this community
post is about that recipe" (`GalleryPost.recipe`, nullable `SET_NULL`).
The community post composer therefore has to turn a recipe the user
browsed and picked into an id, and no endpoint could do that:

- `GET /recipes/` and `GET /recipes/{slug}/` returned no id;
- there is no `GET /recipes/by-id/{id}/` or slug→id resolver;
- the only place a recipe id appeared was inside *other* apps' payloads
  (`_RecipeRefSerializer` in gallery and qa), i.e. only for recipes that
  already had a post or thread attached — useless for attaching the
  first one.

So the omission was not a privacy boundary. The value is already public
wherever a reference card renders; recipe payloads were simply
inconsistent with the rest of the API, and that inconsistency blocked a
documented relationship.

## Decision

Add a read-only `id` to `RecipeListItemSerializer` (and therefore to
`RecipeDetailSerializer`, which extends it).

Slug remains the addressing identity: no route changes, no client is
expected to build a URL from the id. The field exists so that a caller
can populate another app's `recipe_id` write field.

## Consequences

**Positive**

- The community post composer can attach a recipe the user picked from
  the real public recipe feed, using the backend's own FK — no parallel
  slug-based attachment contract, no duplicated recipe data inside posts.
- Recipe payloads are now consistent with courses, lessons, reviews,
  gallery posts and Q&A threads, all of which expose their id.

**Negative / accepted**

- Recipe primary keys become enumerable from the recipe feed, which
  leaks the approximate number of recipes ever created. The same
  inference was already available from gallery and Q&A reference cards,
  and visibility is still enforced per row — an id grants no access.

**Rejected alternatives**

- *Accept `recipe_slug` on gallery post create.* Adds a second way to
  name the same relationship in a write contract that already has one,
  and pushes slug resolution into an app that has no business knowing
  recipe URL rules.
- *A slug→id lookup endpoint.* An endpoint whose entire purpose is to
  undo a deliberate omission is worse than removing the omission.
- *Leave it missing and drop the attachment feature.* The relationship
  exists in the data model and the write contract; the read side simply
  had a hole.

## Frontend note

`MAX_RECIPE_COMMUNITY_POSTS` (frontend constant) bounds how many
attached posts a recipe page shows before linking to the filtered feed.
The backend has no such limit because `GET /gallery/?recipe_id=` is
paginated like every other list.
