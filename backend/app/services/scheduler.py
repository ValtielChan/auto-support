"""Background scheduler: a single tick that runs due mailboxes.

Using one periodic tick (instead of one APScheduler job per mailbox) keeps
interval changes trivial — the next tick simply picks up the new value.
"""

import logging

from apscheduler.schedulers.background import BackgroundScheduler

from ..config import settings
from .agent_runner import process_due_mailboxes

logger = logging.getLogger("autosupport.scheduler")

scheduler = BackgroundScheduler()


def start() -> None:
    scheduler.add_job(
        process_due_mailboxes,
        "interval",
        seconds=settings.scheduler_tick_seconds,
        id="tick",
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    logger.info("Scheduler started (tick every %ss)", settings.scheduler_tick_seconds)


def stop() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
