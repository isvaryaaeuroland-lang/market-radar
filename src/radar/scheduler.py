"""APScheduler wrapper: one recurring job that walks the watchlist and runs
a watch-cycle (crawl + diff + alert) for each domain."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

from .pipeline import run_watch_cycle
from .storage import list_watchlist

logger = logging.getLogger(__name__)


def _run_all_watch_cycles() -> None:
    domains = [row["domain"] for row in list_watchlist()]
    if not domains:
        logger.info("Watchlist is empty — nothing to check.")
        return

    for domain in domains:
        try:
            result = asyncio.run(run_watch_cycle(domain))
            if result is None:
                logger.info("%s: baseline established.", domain)
            elif result.has_material_change:
                logger.info("%s: material change detected and alerted.", domain)
            else:
                logger.info("%s: checked, no material change.", domain)
        except Exception:  # noqa: BLE001 — one domain failing must not stop the cycle
            logger.exception("Watch cycle failed for %s", domain)


def build_scheduler(interval_minutes: int = 10080) -> BackgroundScheduler:
    """Default interval is weekly (10080 minutes). Pass a small value for
    demo purposes so a change fires within the demo window (see SOP §4)."""
    scheduler = BackgroundScheduler()
    scheduler.add_job(_run_all_watch_cycles, "interval", minutes=interval_minutes, next_run_time=datetime.now())
    return scheduler
