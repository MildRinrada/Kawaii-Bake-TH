"""Backfill legal names for accounts that predate the requirement.

Registration now demands a first and last name because certificates print
them. Accounts created before that rule would otherwise leave certificates
falling back to handles, so the known development accounts get their
names here and every other pre-existing row gets a readable placeholder
derived from its handle.

Reversible: the reverse operation clears exactly the rows this migration
filled (names on rows whose consent stamp is still null  i.e. accounts
that never went through the new registration flow).
"""

from __future__ import annotations

from django.db import migrations

# Development seed accounts. Fictional names for fictional bakers; the
# admin account uses the display name its profile already carried.
KNOWN_NAMES: dict[str, tuple[str, str]] = {
    "mildadmin": ("Rinrada", "Laiad"),
    "mildrinrada": ("Rinrada", "Laiad"),
    "mildbakes": ("มินตรา", "อบอุ่น"),
    "chefmaprang": ("มะปราง", "จันทร์หอม"),
    "p16fan0": ("ฟ้าใส", "รักขนม"),
    "p16fan1": ("น้ำหวาน", "อบดี"),
    "p16fan2": ("ต้นข้าว", "หอมกรุ่น"),
}


def seed_names(apps, schema_editor):
    User = apps.get_model("users", "User")
    for user in User.objects.filter(first_name="", last_name=""):
        known = KNOWN_NAMES.get(user.username)
        if known:
            user.first_name, user.last_name = known
        else:
            # A readable stand-in, clearly not a verified legal name:
            # certificates for these accounts print the handle-derived
            # form until the owner provides a real one.
            user.first_name = user.username.capitalize()
            user.last_name = ""
        user.save(update_fields=["first_name", "last_name"])


def unseed_names(apps, schema_editor):
    User = apps.get_model("users", "User")
    # Only rows this migration could have touched: accounts that never
    # accepted terms (post-rule registrations always stamp consent).
    User.objects.filter(terms_accepted_at__isnull=True).update(
        first_name="", last_name=""
    )


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0004_user_first_name_user_last_name_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_names, unseed_names),
    ]
