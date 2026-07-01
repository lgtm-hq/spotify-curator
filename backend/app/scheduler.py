"""Scheduled discovery jobs."""

from __future__ import annotations

import logging

import yaml
from apscheduler.schedulers.background import BackgroundScheduler

from app.db import SessionLocal

logger = logging.getLogger(__name__)
_scheduler: BackgroundScheduler | None = None


def _run_scheduled_discovery() -> None:
    """Run weekly discovery job."""
    import asyncio

    from app.discover.service import generate_discovery_playlist
    from app.spotify_client import get_spotify_client

    async def _run() -> None:
        db = SessionLocal()
        try:
            sp = await get_spotify_client(db)
            result = generate_discovery_playlist(sp, db=db)
            logger.info("Scheduled discovery created playlist: %s", result.get("name"))
        except Exception:
            logger.exception("Scheduled discovery failed")
        finally:
            db.close()

    asyncio.run(_run())


def start_scheduler() -> None:
    """Start APScheduler if cron configured."""
    global _scheduler
    try:
        with open("config.yaml") as f:
            data = yaml.safe_load(f) or {}
        cron = (data.get("discover") or {}).get("schedule_cron", "0 9 * * 1")
    except FileNotFoundError:
        cron = "0 9 * * 1"

    _scheduler = BackgroundScheduler()
    parts = cron.split()
    if len(parts) == 5:
        minute, hour, day, month, day_of_week = parts
        _scheduler.add_job(
            _run_scheduled_discovery,
            trigger="cron",
            minute=minute,
            hour=hour,
            day=day,
            month=month,
            day_of_week=day_of_week,
            id="weekly_discover",
            replace_existing=True,
        )
    _scheduler.start()
    logger.info("Scheduler started with cron: %s", cron)


def stop_scheduler() -> None:
    """Stop scheduler."""
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
