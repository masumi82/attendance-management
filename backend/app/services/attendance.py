from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.attendance_punch import AttendancePunch, PunchSource, PunchType
from app.models.daily_attendance import DailyAttendance, DailyAttendanceStatus
from app.models.monthly_closing import MonthlyClosing

JST = ZoneInfo("Asia/Tokyo")
STANDARD_WORK_MINUTES = 8 * 60  # 所定労働 8h
NIGHT_START = time(22, 0)
NIGHT_END = time(5, 0)


class PunchError(Exception):
    """Punch transition rule violation."""


def jst_date(dt: datetime) -> date:
    return dt.astimezone(JST).date()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def record_punch(
    db: Session,
    *,
    employee_id: UUID,
    punch_type: PunchType,
    punched_at: datetime | None = None,
    source: PunchSource = PunchSource.WEB,
    ip_address: str | None = None,
) -> AttendancePunch:
    now = punched_at or datetime.now(UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    work_date = jst_date(now)

    if _is_closed(db, employee_id=employee_id, work_date=work_date):
        raise PunchError("month_closed")

    today_punches = _punches_for_day(db, employee_id, work_date)
    _validate_transition(punch_type, today_punches)

    punch = AttendancePunch(
        employee_id=employee_id,
        work_date=work_date,
        punched_at=now,
        type=punch_type,
        source=source,
        ip_address=ip_address,
    )
    db.add(punch)
    db.flush()

    recompute_daily(db, employee_id=employee_id, work_date=work_date, now=now)
    return punch


def recompute_daily(
    db: Session,
    *,
    employee_id: UUID,
    work_date: date,
    now: datetime | None = None,
) -> DailyAttendance:
    reference_now = (now or datetime.now(UTC)).astimezone(UTC)
    punches = _punches_for_day(db, employee_id, work_date)

    metrics = _compute_metrics(punches, reference_now=reference_now, work_date=work_date)

    stmt = (
        select(DailyAttendance)
        .where(DailyAttendance.employee_id == employee_id)
        .where(DailyAttendance.work_date == work_date)
    )
    existing = db.execute(stmt).scalar_one_or_none()
    if existing is None:
        existing = DailyAttendance(employee_id=employee_id, work_date=work_date)
        db.add(existing)

    existing.first_clock_in_at = metrics["first_in"]
    existing.last_clock_out_at = metrics["last_out"]
    existing.worked_minutes = metrics["worked"]
    existing.break_minutes = metrics["break_minutes"]
    existing.overtime_minutes = metrics["overtime"]
    existing.night_minutes = metrics["night"]
    existing.status = metrics["status"]
    db.flush()
    return existing


def get_daily(
    db: Session, *, employee_id: UUID, work_date: date
) -> DailyAttendance | None:
    stmt = (
        select(DailyAttendance)
        .where(DailyAttendance.employee_id == employee_id)
        .where(DailyAttendance.work_date == work_date)
    )
    return db.execute(stmt).scalar_one_or_none()


def list_punches(
    db: Session, *, employee_id: UUID, work_date: date
) -> list[AttendancePunch]:
    return _punches_for_day(db, employee_id, work_date)


def list_month(
    db: Session, *, employee_id: UUID, year: int, month: int
) -> list[DailyAttendance]:
    start = date(year, month, 1)
    end = date(year + (1 if month == 12 else 0), 1 if month == 12 else month + 1, 1)
    stmt = (
        select(DailyAttendance)
        .where(DailyAttendance.employee_id == employee_id)
        .where(DailyAttendance.work_date >= start)
        .where(DailyAttendance.work_date < end)
        .order_by(DailyAttendance.work_date.asc())
    )
    return list(db.execute(stmt).scalars().all())


def punch_state(punches: list[AttendancePunch]) -> str:
    """Returns logical state: 'none' | 'working' | 'on_break' | 'done'."""
    has_clock_in = any(p.type == PunchType.CLOCK_IN for p in punches)
    has_clock_out = any(p.type == PunchType.CLOCK_OUT for p in punches)
    if not has_clock_in:
        return "none"
    if has_clock_out:
        return "done"
    on_break = False
    for p in punches:
        if p.type == PunchType.BREAK_START:
            on_break = True
        elif p.type == PunchType.BREAK_END:
            on_break = False
    return "on_break" if on_break else "working"


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------
def _is_closed(db: Session, *, employee_id: UUID, work_date: date) -> bool:
    ym = f"{work_date.year:04d}-{work_date.month:02d}"
    stmt = select(MonthlyClosing).where(
        MonthlyClosing.employee_id == employee_id,
        MonthlyClosing.year_month == ym,
        MonthlyClosing.closed_at.isnot(None),
    )
    return db.execute(stmt).scalar_one_or_none() is not None


def _punches_for_day(
    db: Session, employee_id: UUID, work_date: date
) -> list[AttendancePunch]:
    stmt = (
        select(AttendancePunch)
        .where(AttendancePunch.employee_id == employee_id)
        .where(AttendancePunch.work_date == work_date)
        .order_by(AttendancePunch.punched_at.asc())
    )
    return list(db.execute(stmt).scalars().all())


def _validate_transition(
    new_type: PunchType, today: list[AttendancePunch]
) -> None:
    state = punch_state(today)
    has_clock_out = any(p.type == PunchType.CLOCK_OUT for p in today)

    if new_type == PunchType.CLOCK_IN:
        if state != "none":
            raise PunchError("already_clocked_in")
        return
    if new_type == PunchType.BREAK_START:
        if state == "none":
            raise PunchError("not_clocked_in")
        if state == "on_break":
            raise PunchError("already_on_break")
        if state == "done":
            raise PunchError("already_clocked_out")
        return
    if new_type == PunchType.BREAK_END:
        if state != "on_break":
            raise PunchError("not_on_break")
        return
    if new_type == PunchType.CLOCK_OUT:
        if state == "none":
            raise PunchError("not_clocked_in")
        if state == "on_break":
            raise PunchError("still_on_break")
        if has_clock_out:
            raise PunchError("already_clocked_out")
        return


def _compute_metrics(
    punches: list[AttendancePunch],
    *,
    reference_now: datetime,
    work_date: date,
) -> dict:
    clock_ins = [p for p in punches if p.type == PunchType.CLOCK_IN]
    clock_outs = [p for p in punches if p.type == PunchType.CLOCK_OUT]
    break_starts = [p for p in punches if p.type == PunchType.BREAK_START]
    break_ends = [p for p in punches if p.type == PunchType.BREAK_END]

    first_in = clock_ins[0].punched_at if clock_ins else None
    last_out = clock_outs[-1].punched_at if clock_outs else None

    if first_in is None:
        return {
            "first_in": None,
            "last_out": None,
            "worked": 0,
            "break_minutes": 0,
            "overtime": 0,
            "night": 0,
            "status": DailyAttendanceStatus.PENDING,
        }

    today_jst = jst_date(reference_now)
    # 退勤未打刻で過去日なら pending のまま 0
    if last_out is None and work_date < today_jst:
        return {
            "first_in": first_in,
            "last_out": None,
            "worked": 0,
            "break_minutes": 0,
            "overtime": 0,
            "night": 0,
            "status": DailyAttendanceStatus.PENDING,
        }

    end: datetime = last_out if last_out is not None else reference_now

    break_intervals: list[tuple[datetime, datetime]] = []
    for idx, bs in enumerate(break_starts):
        if idx < len(break_ends):
            be = break_ends[idx].punched_at
        else:
            # open break (only for today)
            be = reference_now if work_date == today_jst else bs.punched_at
        if bs.punched_at < be:
            break_intervals.append((bs.punched_at, be))

    total_span_min = _minutes_between(first_in, end)
    break_min = sum(_minutes_between(bs, be) for bs, be in break_intervals)
    worked = max(0, total_span_min - break_min)
    overtime = max(0, worked - STANDARD_WORK_MINUTES)

    working_intervals = _subtract_intervals((first_in, end), break_intervals)
    night = sum(_night_minutes(s, e) for s, e in working_intervals)

    status = (
        DailyAttendanceStatus.NORMAL
        if last_out is not None
        else DailyAttendanceStatus.PENDING
    )
    return {
        "first_in": first_in,
        "last_out": last_out,
        "worked": worked,
        "break_minutes": break_min,
        "overtime": overtime,
        "night": night,
        "status": status,
    }


def _minutes_between(a: datetime, b: datetime) -> int:
    return max(0, int((b - a).total_seconds()) // 60)


def _subtract_intervals(
    window: tuple[datetime, datetime],
    subs: list[tuple[datetime, datetime]],
) -> list[tuple[datetime, datetime]]:
    result: list[tuple[datetime, datetime]] = [window]
    for s, e in subs:
        new_result: list[tuple[datetime, datetime]] = []
        for ws, we in result:
            if e <= ws or s >= we:
                new_result.append((ws, we))
            else:
                if s > ws:
                    new_result.append((ws, s))
                if e < we:
                    new_result.append((e, we))
        result = new_result
    return result


def _night_minutes(start: datetime, end: datetime) -> int:
    if start >= end:
        return 0
    start_jst = start.astimezone(JST)
    end_jst = end.astimezone(JST)
    total = 0
    cur = start_jst
    while cur < end_jst:
        day = cur.date()
        next_day = day + timedelta(days=1)
        day_end = datetime.combine(next_day, time.min, tzinfo=JST)
        segment_end = min(end_jst, day_end)
        windows = [
            (
                datetime.combine(day, NIGHT_START, tzinfo=JST),
                datetime.combine(next_day, time.min, tzinfo=JST),
            ),
            (
                datetime.combine(day, time.min, tzinfo=JST),
                datetime.combine(day, NIGHT_END, tzinfo=JST),
            ),
        ]
        for ws, we in windows:
            overlap_start = max(cur, ws)
            overlap_end = min(segment_end, we)
            if overlap_start < overlap_end:
                total += int((overlap_end - overlap_start).total_seconds()) // 60
        cur = segment_end
    return total


__all__ = [
    "PunchError",
    "get_daily",
    "jst_date",
    "list_month",
    "list_punches",
    "punch_state",
    "record_punch",
    "recompute_daily",
]
