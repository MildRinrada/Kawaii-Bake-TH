"""Ready-made recipe content, twenty per active category.

This is **seed data, not a fixture**: it is loaded by
``manage.py seed_recipes``, which routes every write through the recipes
repositories, so the rows it produces are indistinguishable from ones an author
created through the API.

Why not a Django fixture: a fixture pins primary keys and the author id, cannot
resolve category slugs, and silently overwrites whatever already sits on those
ids. Why not a data migration: this content is demo material that a deployment
may legitimately not want, and a migration would force it on every database.

Each entry owns an explicit English ``slug``. That slug is the identity the
command de-duplicates on, which is what makes re-running it safe.

Cover images are deliberately absent  they are attached separately, and the
command therefore publishes without the ``cover_image`` completeness check.
"""

from __future__ import annotations

from typing import Any

from apps.recipes.seeds import bread, cake, chocolate, cookies, macaron, pastry, pie
from apps.recipes.seeds.loader import build_payload

# Keyed by category slug, in the taxonomy's own display order.
SEEDS_BY_CATEGORY: dict[str, list[dict[str, Any]]] = {
    "bread": bread.RECIPES,
    "cake": cake.RECIPES,
    "cookies": cookies.RECIPES,
    "pastry": pastry.RECIPES,
    "pie": pie.RECIPES,
    "macaron": macaron.RECIPES,
    "chocolate": chocolate.RECIPES,
}

__all__ = ["SEEDS_BY_CATEGORY", "build_payload"]
