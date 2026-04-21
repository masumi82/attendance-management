"""APScheduler wiring. Currently runs a daily overtime check."""

from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.db.session import SessionLocal
from app.services import overtime as overtime_service

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")
_scheduler: BackgroundScheduler | None = None


def _run_daily_overtime_check() -> None:
    now = datetime.now(JST)
    try:
        with SessionLocal() as db:
            sent = overtime_service.run_all_employees_check(
                db, year=now.year, month=now.month
            )
            db.commit()
        logger.info("daily overtime check done (alerts=%d)", sent)
    except Exception:  # noqa: BLE001
        logger.exception("daily overtime check failed")


def start_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        return
    scheduler = BackgroundScheduler(timezone=JST)
    # Daily at 00:30 JST
    scheduler.add_job(
        _run_daily_overtime_check,
        trigger=CronTrigger(hour=0, minute=30, timezone=JST),
        id="daily_overtime_check",
        replace_existing=True,
    )
    scheduler.start()
    _scheduler = scheduler
    logger.info("scheduler started (jobs=%s)", [j.id for j in scheduler.get_jobs()])


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is None:
        return
    _scheduler.shutdown(wait=False)
    _scheduler = None
    logger.info("scheduler stopped")
