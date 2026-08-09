"""Seed the taxonomy from ``users.constants.BakingCategory``.

``Profile.favorite_categories`` already stores those slugs as JSON. Seeding the
identical slugs here is what makes the eventual JSON-to-many-to-many backfill an
exact match rather than a manual reconciliation.

The labels are imported at migration time deliberately: this is a one-off seed
of the *current* enum, and the resulting rows become editable data owned by
staff from then on.
"""

from __future__ import annotations

from django.db import migrations

# Frozen copy of the enum as it stood when this migration was written.
# Migrations must not import live application code — a later edit to the enum
# would silently change what this historical migration does.
SEED_CATEGORIES: list[tuple[str, str, int]] = [
    ("bread", "Bread", 10),
    ("cake", "Cake", 20),
    ("cookies", "Cookies", 30),
    ("pastry", "Pastry", 40),
    ("pie", "Pie & Tart", 50),
    ("macaron", "Macaron", 60),
    ("chocolate", "Chocolate", 70),
    ("decorating", "Cake Decorating", 80),
    ("vegan", "Vegan Baking", 90),
    ("gluten_free", "Gluten Free", 100),
]


def seed_categories(apps, schema_editor) -> None:
    """Create the initial categories, skipping any that already exist."""
    RecipeCategory = apps.get_model("recipe_categories", "RecipeCategory")

    existing = set(RecipeCategory.objects.values_list("slug", flat=True))
    RecipeCategory.objects.bulk_create(
        [
            RecipeCategory(slug=slug, name=name, display_order=order, is_active=True)
            for slug, name, order in SEED_CATEGORIES
            if slug not in existing
        ]
    )


def unseed_categories(apps, schema_editor) -> None:
    """Remove the seeded categories.

    Only removes rows still matching a seeded slug; anything staff have added
    since is left alone.
    """
    RecipeCategory = apps.get_model("recipe_categories", "RecipeCategory")
    RecipeCategory.objects.filter(
        slug__in=[slug for slug, _name, _order in SEED_CATEGORIES]
    ).delete()


class Migration(migrations.Migration):
    """Seed the recipe category taxonomy."""

    dependencies = [
        ("recipe_categories", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_categories, unseed_categories),
    ]
