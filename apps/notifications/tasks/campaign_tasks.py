"""The scheduled-campaign dispatcher (ADR 0030).

Scheduling is honest only if something actually fires: this task is on
``CELERY_BEAT_SCHEDULE`` (one scan per minute) for deployments running
``celery -A config beat``, and the same service call backs the
``dispatch_campaigns`` management command for cron-style setups. A
deployment running neither still sees due campaigns flagged in the admin
UI, with a manual send button.
"""

from __future__ import annotations

from celery import shared_task

from apps.notifications.services import campaign_service


@shared_task(name="notifications.dispatch_due_campaigns")
def dispatch_due_campaigns_task() -> int:
    """Send every scheduled campaign whose time has come.

    Returns:
        How many campaigns were sent.
    """
    return campaign_service.dispatch_due_campaigns()
