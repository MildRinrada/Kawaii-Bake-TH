"""Announcement kinds become a closed set, and clicks become countable.

The retired ``icon`` column held an emoji the composer used to ask for;
nothing has rendered it since announcements started drawing their glyph
from the kind, so removing it loses decoration, not information.

``kind`` was a free slug defaulting to ``"custom"`` - a value the new
closed set has no drawing for. Existing rows are mapped onto it, and
delivered announcements are backfilled from the campaign they came from
so an inbox opened after this deploy looks the same as one opened
before.
"""

from django.db import migrations, models

VALID_KINDS = {"general", "feature", "event", "maintenance", "policy", "alert"}


def normalize_kinds(apps, schema_editor):
    """Map free-form kinds onto the closed set, then backfill deliveries."""
    Campaign = apps.get_model("notifications", "NotificationCampaign")
    Template = apps.get_model("notifications", "NotificationTemplate")
    Notification = apps.get_model("notifications", "Notification")

    for model in (Campaign, Template):
        model.objects.exclude(kind__in=VALID_KINDS).update(kind="general")

    for campaign in Campaign.objects.all():
        Notification.objects.filter(campaign_id=campaign.pk).update(
            kind=campaign.kind if campaign.kind in VALID_KINDS else "general"
        )
    # Announcements sent before campaigns existed have no campaign to read
    # from; "general" is what they were.
    Notification.objects.filter(event_type="announcement", kind="").update(
        kind="general"
    )


def clear_kinds(apps, schema_editor):
    """Reverse: the column is about to be dropped, so only blank it."""
    Notification = apps.get_model("notifications", "Notification")
    Notification.objects.update(kind="")


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0005_alter_notification_event_type_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='notification',
            name='icon',
        ),
        migrations.RemoveField(
            model_name='notificationcampaign',
            name='icon',
        ),
        migrations.RemoveField(
            model_name='notificationtemplate',
            name='icon',
        ),
        migrations.AddField(
            model_name='notification',
            name='clicked_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='notification',
            name='kind',
            field=models.CharField(blank=True, choices=[('general', 'General announcement'), ('feature', 'New feature'), ('event', 'Event or campaign'), ('maintenance', 'Scheduled maintenance'), ('policy', 'Policy or terms change'), ('alert', 'Urgent notice')], max_length=40),
        ),
        migrations.AlterField(
            model_name='notificationcampaign',
            name='kind',
            field=models.CharField(choices=[('general', 'General announcement'), ('feature', 'New feature'), ('event', 'Event or campaign'), ('maintenance', 'Scheduled maintenance'), ('policy', 'Policy or terms change'), ('alert', 'Urgent notice')], default='general', max_length=40),
        ),
        migrations.AlterField(
            model_name='notificationtemplate',
            name='kind',
            field=models.CharField(choices=[('general', 'General announcement'), ('feature', 'New feature'), ('event', 'Event or campaign'), ('maintenance', 'Scheduled maintenance'), ('policy', 'Policy or terms change'), ('alert', 'Urgent notice')], default='general', max_length=40),
        ),
        migrations.RunPython(normalize_kinds, clear_kinds),
    ]
