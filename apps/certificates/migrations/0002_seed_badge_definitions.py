"""Seed the badge definitions — one per achievement type, bilingual.

Badges are system-owned data with no CRUD API, so the initial set ships as
a data migration (the prompt-template precedent, Phase 7). Curation happens
in Django admin; slugs are identities and never change.
"""

from __future__ import annotations

from django.db import migrations

_BADGES = [
    (
        "course_completed",
        "จบคอร์สแรกสำเร็จ",
        "Course completed",
        "เรียนจบครบทุกบทเรียนของคอร์สหนึ่งคอร์ส",
        "Finished every lesson of a course.",
        "🎓",
    ),
    (
        "first_course",
        "ก้าวแรกของนักอบ",
        "First course",
        "จบคอร์สแรกของคุณบน KawaiiBake",
        "Completed your very first KawaiiBake course.",
        "🌱",
    ),
    (
        "ten_courses",
        "นักเรียนตัวยง",
        "Ten courses",
        "จบคอร์สครบ 10 คอร์ส",
        "Completed ten courses.",
        "🏆",
    ),
    (
        "quiz_master",
        "เซียนควิซ",
        "Quiz master",
        "ผ่านควิซด้วยคะแนนยอดเยี่ยม",
        "Aced the quizzes.",
        "🧠",
    ),
    (
        "recipe_author",
        "เชฟนักแต่งสูตร",
        "Recipe author",
        "เผยแพร่สูตรของตัวเอง",
        "Published your own recipe.",
        "📖",
    ),
]


def seed_badges(apps, schema_editor):
    """Create every badge definition, active."""
    BadgeDefinition = apps.get_model("certificates", "BadgeDefinition")
    BadgeDefinition.objects.bulk_create(
        BadgeDefinition(
            slug=slug,
            title_th=title_th,
            title_en=title_en,
            description_th=description_th,
            description_en=description_en,
            icon=icon,
            is_active=True,
        )
        for slug, title_th, title_en, description_th, description_en, icon in _BADGES
    )


def unseed_badges(apps, schema_editor):
    """Remove exactly the seeded rows."""
    BadgeDefinition = apps.get_model("certificates", "BadgeDefinition")
    BadgeDefinition.objects.filter(
        slug__in=[badge[0] for badge in _BADGES]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("certificates", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_badges, unseed_badges),
    ]
