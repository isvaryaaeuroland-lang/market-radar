"""Standalone continuous-monitoring process (SOP §4). Run with:

    python -m radar.scheduler_daemon [--interval-minutes N]
"""
from __future__ import annotations

import argparse
import logging
import time

from .scheduler import build_scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Radar's continuous watchlist monitor.")
    parser.add_argument(
        "--interval-minutes",
        type=int,
        default=10080,
        help="Re-check interval in minutes (default: 10080 = weekly). Use a small value for demos.",
    )
    args = parser.parse_args()

    scheduler = build_scheduler(interval_minutes=args.interval_minutes)
    scheduler.start()
    logging.info("Radar monitoring daemon started, checking every %d minutes. Ctrl+C to stop.", args.interval_minutes)

    try:
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()


if __name__ == "__main__":
    main()
