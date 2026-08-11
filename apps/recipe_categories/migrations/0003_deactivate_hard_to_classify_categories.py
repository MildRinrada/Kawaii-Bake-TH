"""Deactivate three categories that turned out hard to classify.

"Cake Decorating", "Vegan Baking" and "Gluten Free" describe a *technique*
or *dietary constraint* that cuts across every other category rather than
sitting beside them  a macaron can be vegan, a cake can be decorated,
neither fact tells you what to bake. In practice this made them attract
mis-tagged recipes and left authors guessing which single category to
pick.

Deactivating (not deleting) uses the field the model already documents
for exactly this: "Inactive categories stay assigned but are hidden from
listings." No recipe or course currently references any of the three, so
this is a pure visibility change  reversible, and nothing to reassign.
"""

from __future__ import annotations

from django.db import migrations

_SLUGS = ["decorating", "vegan", "gluten_free"]


def deactivate(apps, schema_editor):
    """Hide the three categories from listings."""
    RecipeCategory = apps.get_model("recipe_categories", "RecipeCategory")
    RecipeCategory.objects.filter(slug__in=_SLUGS).update(is_active=False)


def reactivate(apps, schema_editor):
    """Reverse: restore their previous visibility."""
    RecipeCategory = apps.get_model("recipe_categories", "RecipeCategory")
    RecipeCategory.objects.filter(slug__in=_SLUGS).update(is_active=True)


class Migration(migrations.Migration):
    dependencies = [
        ("recipe_categories", "0002_seed_from_baking_category"),
    ]

    operations = [
        migrations.RunPython(deactivate, reactivate),
    ]
