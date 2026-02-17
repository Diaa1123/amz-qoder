"""AMZ_Designy - APScheduler setup for daily and weekly jobs."""

from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import AppConfig

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


async def _daily_job(config: AppConfig) -> None:
    from app.orchestrator import run_daily

    try:
        report = await run_daily(config)
        logger.info("Scheduled daily job: %d niches", len(report.entries))
    except Exception:
        logger.exception("Scheduled daily job failed")


async def _weekly_job(config: AppConfig) -> None:
    from app.orchestrator import run_weekly

    try:
        ids = await run_weekly(config)
        logger.info("Scheduled weekly job: %d ideas published", len(ids))
    except Exception:
        logger.exception("Scheduled weekly job failed")


def init_scheduler(config: AppConfig) -> AsyncIOScheduler:
    """Create and start the APScheduler with daily and weekly jobs."""
    global _scheduler  # noqa: PLW0603

    scheduler = AsyncIOScheduler(timezone=config.timezone)

    # Parse daily_run_time "HH:MM"
    parts = config.daily_run_time.split(":")
    hour, minute = int(parts[0]), int(parts[1])

    scheduler.add_job(
        _daily_job,
        CronTrigger(hour=hour, minute=minute),
        args=[config],
        id="daily_pipeline",
        replace_existing=True,
        misfire_grace_time=3600,
        max_instances=1,
    )

    scheduler.add_job(
        _weekly_job,
        CronTrigger(day_of_week=config.weekly_run_day, hour=hour + 1, minute=0),
        args=[config],
        id="weekly_pipeline",
        replace_existing=True,
        misfire_grace_time=7200,
        max_instances=1,
    )

    scheduler.start()
    _scheduler = scheduler
    logger.info(
        "Scheduler started (daily=%s, weekly=day %d, tz=%s)",
        config.daily_run_time,
        config.weekly_run_day,
        config.timezone,
    )
    return scheduler


async def shutdown_scheduler() -> None:
    """Gracefully shut down the scheduler."""
    global _scheduler  # noqa: PLW0603
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler shut down")
        _scheduler = None
