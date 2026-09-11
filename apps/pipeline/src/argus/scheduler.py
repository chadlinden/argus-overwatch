"""In-process daily trigger. Default container CMD. Runs pipeline.run() once at
startup, then every day at the configured hour/minute (local/UTC container time).
"""

from __future__ import annotations

import logging
import os

from apscheduler.schedulers.blocking import BlockingScheduler

from .config import Settings
from .pipeline import run

logger = logging.getLogger("argus.scheduler")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = Settings()
    schedule_hour = int(os.environ.get("ARGUS_SCHEDULE_HOUR", "6"))
    schedule_minute = int(os.environ.get("ARGUS_SCHEDULE_MINUTE", "0"))

    logger.info("running pipeline once at startup")
    run(settings)

    scheduler = BlockingScheduler()
    scheduler.add_job(
        run,
        "cron",
        hour=schedule_hour,
        minute=schedule_minute,
        args=[settings],
        id="argus_daily_run",
    )
    logger.info("scheduled daily run at %02d:%02d container time", schedule_hour, schedule_minute)
    scheduler.start()


if __name__ == "__main__":
    main()
