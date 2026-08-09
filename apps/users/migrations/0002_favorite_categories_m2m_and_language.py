"""Phase 14: the promised favorite-categories backfill, and Thai-first locale.

ADR 0006 stored favourite categories as canonical slugs precisely so this
migration would be an exact match: the JSON column is renamed aside, the
real many-to-many to ``recipe_categories`` is added, every stored slug is
resolved against the (Phase 2-seeded) taxonomy and linked, and the JSON
column is dropped. Slugs that no longer resolve are dropped silently —
they pointed at nothing a user could select anyway.

``locale`` narrows from free text nothing consumed ("en-us" default) to
the assistant-compatible ``th``/``en`` set with a Thai default; existing
values map by language family (``th*`` → ``th``, everything else →
``en``), preserving the only information the old field carried.
"""

from __future__ import annotations

from django.db import migrations, models


def backfill(apps, schema_editor):
    """Link each profile's stored slugs to real taxonomy rows."""
    Profile = apps.get_model("users", "Profile")
    RecipeCategory = apps.get_model("recipe_categories", "RecipeCategory")
    by_slug = {row.slug: row.pk for row in RecipeCategory.objects.all()}

    for profile in Profile.objects.exclude(favorite_categories_legacy=[]):
        ids = [
            by_slug[slug]
            for slug in (profile.favorite_categories_legacy or [])
            if slug in by_slug
        ]
        if ids:
            profile.favorite_categories.set(ids)

    UserPreference = apps.get_model("users", "UserPreference")
    UserPreference.objects.filter(locale__istartswith="th").update(locale="th")
    UserPreference.objects.exclude(locale="th").update(locale="en")


def noop(apps, schema_editor):
    """Reverse: the M2M table is dropped by the schema reversal."""


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0001_initial"),
        ("recipe_categories", "0002_seed_from_baking_category"),
    ]

    operations = [
        migrations.RenameField(
            model_name="profile",
            old_name="favorite_categories",
            new_name="favorite_categories_legacy",
        ),
        migrations.AddField(
            model_name="profile",
            name="favorite_categories",
            field=models.ManyToManyField(
                blank=True, related_name="+", to="recipe_categories.recipecategory"
            ),
        ),
        migrations.AlterField(
            model_name="userpreference",
            name="locale",
            field=models.CharField(
                choices=[("th", "Thai"), ("en", "English")],
                default="th",
                max_length=10,
            ),
        ),
        migrations.RunPython(backfill, noop),
        migrations.RemoveField(
            model_name="profile",
            name="favorite_categories_legacy",
        ),
    ]
