"""Send every due scheduled campaign - the cron-friendly dispatcher."""

from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.notifications.services import campaign_service


class Command(BaseCommand):
    """Dispatch scheduled notification campaigns whose time has come."""

    help = "Send every scheduled notification campaign that is due."

    def handle(self, *args: object, **options: object) -> None:
        """Run one dispatch scan and report the count."""
        sent = campaign_service.dispatch_due_campaigns()
        self.stdout.write(self.style.SUCCESS(f"Dispatched {sent} campaign(s)."))
