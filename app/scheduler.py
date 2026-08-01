import logging
import os

from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)
_scheduler = AsyncIOScheduler(timezone="Europe/Berlin")


def start(scrape_fn):
    interval_hours = float(os.getenv("SCRAPE_INTERVAL_HOURS", "4"))
    _scheduler.add_job(
        scrape_fn,
        "interval",
        hours=interval_hours,
        id="scrape_all",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info("Scheduler gestartet: Scraping alle %.1fh", interval_hours)


def stop():
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
