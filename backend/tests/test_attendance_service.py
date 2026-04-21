from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy.orm import Session

from app.models.attendance_punch import PunchType
from app.models.daily_attendance import DailyAttendanceStatus
from app.models.employee import Employee
from app.services import attendance as att

JST = ZoneInfo("Asia/Tokyo")


def _jst(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=JST).astimezone(UTC)


def test_standard_day_work_8h_no_overtime(db_session: Session, member: Employee) -> None:
    # 9:00 IN, 12:00 break_start, 13:00 break_end, 18:00 OUT => worked 8h, break 1h
    in_at = _jst(2026, 4, 21, 9, 0)
    bs = _jst(2026, 4, 21, 12, 0)
    be = _jst(2026, 4, 21, 13, 0)
    out = _jst(2026, 4, 21, 18, 0)

    att.record_punch(db_session, employee_id=member.id, punch_type=PunchType.CLOCK_IN, punched_at=in_at)
    att.record_punch(db_session, employee_id=member.id, punch_type=PunchType.BREAK_START, punched_at=bs)
    att.record_punch(db_session, employee_id=member.id, punch_type=PunchType.BREAK_END, punched_at=be)
    att.record_punch(db_session, employee_id=member.id, punch_type=PunchType.CLOCK_OUT, punched_at=out)
    db_session.commit()

    daily = att.get_daily(db_session, employee_id=member.id, work_date=att.jst_date(in_at))
    assert daily is not None
    assert daily.status is DailyAttendanceStatus.NORMAL
    assert daily.worked_minutes == 8 * 60
    assert daily.break_minutes == 60
    assert daily.overtime_minutes == 0
    assert daily.night_minutes == 0


def test_overtime_and_night_hours(db_session: Session, member: Employee) -> None:
    # 10:00 IN, no break, 23:30 OUT (13.5h worked)
    # overtime = 13.5h - 8h = 5.5h = 330min
    # night = 22:00 -> 23:30 = 90min
    in_at = _jst(2026, 4, 21, 10, 0)
    out = _jst(2026, 4, 21, 23, 30)

    att.record_punch(db_session, employee_id=member.id, punch_type=PunchType.CLOCK_IN, punched_at=in_at)
    att.record_punch(db_session, employee_id=member.id, punch_type=PunchType.CLOCK_OUT, punched_at=out)
    db_session.commit()

    daily = att.get_daily(db_session, employee_id=member.id, work_date=att.jst_date(in_at))
    assert daily is not None
    assert daily.worked_minutes == 13 * 60 + 30
    assert daily.overtime_minutes == 5 * 60 + 30
    assert daily.night_minutes == 90


def test_transition_rules(db_session: Session, member: Employee) -> None:
    # break before clock_in rejected
    with pytest.raises(att.PunchError):
        att.record_punch(
            db_session,
            employee_id=member.id,
            punch_type=PunchType.BREAK_START,
            punched_at=_jst(2026, 4, 21, 9, 0),
        )

    att.record_punch(
        db_session,
        employee_id=member.id,
        punch_type=PunchType.CLOCK_IN,
        punched_at=_jst(2026, 4, 21, 9, 0),
    )

    # second clock_in rejected
    with pytest.raises(att.PunchError):
        att.record_punch(
            db_session,
            employee_id=member.id,
            punch_type=PunchType.CLOCK_IN,
            punched_at=_jst(2026, 4, 21, 9, 30),
        )

    # break_end without break_start rejected
    with pytest.raises(att.PunchError):
        att.record_punch(
            db_session,
            employee_id=member.id,
            punch_type=PunchType.BREAK_END,
            punched_at=_jst(2026, 4, 21, 10, 0),
        )

    att.record_punch(
        db_session,
        employee_id=member.id,
        punch_type=PunchType.BREAK_START,
        punched_at=_jst(2026, 4, 21, 12, 0),
    )

    # clock_out while on break rejected
    with pytest.raises(att.PunchError):
        att.record_punch(
            db_session,
            employee_id=member.id,
            punch_type=PunchType.CLOCK_OUT,
            punched_at=_jst(2026, 4, 21, 12, 30),
        )


def test_pending_when_no_clock_out_today(
    db_session: Session, member: Employee
) -> None:
    in_at = _jst(2026, 4, 21, 9, 0)
    att.record_punch(
        db_session,
        employee_id=member.id,
        punch_type=PunchType.CLOCK_IN,
        punched_at=in_at,
    )
    db_session.commit()
    daily = att.get_daily(db_session, employee_id=member.id, work_date=att.jst_date(in_at))
    assert daily is not None
    assert daily.status is DailyAttendanceStatus.PENDING
