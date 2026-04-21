from __future__ import annotations

import uuid
from datetime import time

from sqlalchemy import Integer, String, Time
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class EmploymentType(Base, TimestampMixin):
    """Work style master: standard / shift / flex."""

    __tablename__ = "employment_types"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    standard_daily_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=480
    )
    standard_weekly_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=2400
    )
    core_start: Mapped[time | None] = mapped_column(Time, nullable=True)
    core_end: Mapped[time | None] = mapped_column(Time, nullable=True)
