"""Replace emoji `icon` values with frontend asset keys.

0002 originally seeded `icon` with an emoji character, on the theory that
the frontend might render it directly. It never did  badge artwork lives
in `frontend/public/achievements/<slug>.svg` and is resolved by *slug*
(`badgeArt()`), not by this field. Storing emoji in an admin-facing
column was purely accidental duplication with no consumer, so this
migration rewrites every seeded row's `icon` to match its own slug 
readable in Django admin, and consistent with what 0002 now seeds for a
fresh database.

Reversible to the original emoji, so a rollback restores exactly what was
there before.
"""

from __future__ import annotations

from django.db import migrations

# slug -> (new asset key, old emoji)  the mapping this migration walks
# in both directions.
_REWRITES = [
    ("course_completed", "course_completed", "\U0001f393"),  # 🎓
    ("first_course", "first_course", "\U0001f331"),  # 🌱
    ("ten_courses", "ten_courses", "\U0001f3c6"),  # 🏆
    ("quiz_master", "quiz_master", "\U0001f9e0"),  # 🧠
    ("recipe_author", "recipe_author", "\U0001f4d6"),  # 📖
]


def use_asset_keys(apps, schema_editor):
    """Rewrite each seeded badge's `icon` to its slug."""
    BadgeDefinition = apps.get_model("certificates", "BadgeDefinition")
    for slug, asset_key, _emoji in _REWRITES:
        BadgeDefinition.objects.filter(slug=slug).update(icon=asset_key)


def restore_emoji(apps, schema_editor):
    """Reverse: put the original emoji back."""
    BadgeDefinition = apps.get_model("certificates", "BadgeDefinition")
    for slug, _asset_key, emoji in _REWRITES:
        BadgeDefinition.objects.filter(slug=slug).update(icon=emoji)


class Migration(migrations.Migration):
    dependencies = [
        ("certificates", "0002_seed_badge_definitions"),
    ]

    operations = [
        migrations.RunPython(use_asset_keys, restore_emoji),
    ]
