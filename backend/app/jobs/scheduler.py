"""APScheduler wiring.

Jobs:
  - daily overtime check (00:30 JST)
  - daily revoked-access-token purge (02:00 JST)

Each job acquires a Postgres advisory lock so that if multiple backend
processes ever run (future multi-worker gunicorn / multi-host setup), only
one will execute the job. Single-process deployment on Raspberry Pi is
also correctly handled by this design.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import text

from app.db.session import SessionLocal
from app.models.revoked_access_token import RevokedAccessToken
from app.services import overtime as overtime_service

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")
_scheduler: BackgroundScheduler | None = None

# Arbitrary 64-bit keys for pg_advisory_lock. Must be stable and unique
# per job so separate jobs don't block each other.
_LOCK_OVERTIME_CHECK = 0x4154_4E44_4F54_0001  # 'ATND' 'OT' 0001
_LOCK_REVOKED_PURGE = 0x4154_4E44_5245_0001  # 'ATND' 'RE' 0001


@contextmanager
def _advisory_lock(db, key: int):
    """Try to acquire a session-scoped Postgres advisory lock. Yields True
    if this process is the holder, False otherwise. The lock is released
    when the session ends (no manual unlock needed).
    """
    got = db.execute(
        text("SELECT pg_try_advisory_lock(:k)"), {"k": key}
    ).scalar()
    try:
        yield bool(got)
    finally:
        if got:
            db.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": key})


def _run_daily_overtime_check() -> None:
    now = datetime.now(JST)
    try:
        with SessionLocal() as db:
            with _advisory_lock(db, _LOCK_OVERTIME_CHECK) as acquired:
                if not acquired:
                    logger.info("overtime check skipped — lock held elsewhere")
                    return
                sent = overtime_service.run_all_employees_check(
                    db, year=now.year, month=now.month
                )
                db.commit()
                logger.info("daily overtime check done (alerts=%d)", sent)
    except Exception:  # noqa: BLE001
        logger.exception("daily overtime check failed")


def _run_purge_revoked_access_tokens() -> None:
    """Remove rows from revoked_access_tokens whose exp has passed."""
    try:
        with SessionLocal() as db:
            with _advisory_lock(db, _LOCK_REVOKED_PURGE) as acquired:
                if not acquired:
                    return
                result = db.execute(
                    text(
                        "DELETE FROM revoked_access_tokens "
                        "WHERE expires_at < now()"
                    )
                )
                deleted = result.rowcount or 0  # type: ignore[attr-defined]
                db.commit()
                if deleted:
                    logger.info("purged %d expired revoked access tokens", deleted)
    except Exception:  # noqa: BLE001
        logger.exception("revoked-token purge failed")


def start_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        return
    scheduler = BackgroundScheduler(timezone=JST)
    scheduler.add_job(
        _run_daily_overtime_check,
        trigger=CronTrigger(hour=0, minute=30, timezone=JST),
        id="daily_overtime_check",
        replace_existing=True,
    )
    scheduler.add_job(
        _run_purge_revoked_access_tokens,
        trigger=CronTrigger(hour=2, minute=0, timezone=JST),
        id="daily_purge_revoked_tokens",
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


__all__ = ["RevokedAccessToken", "start_scheduler", "stop_scheduler"]
