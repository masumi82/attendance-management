from __future__ import annotations

import uuid
from datetime import date as date_

from sqlalchemy import Date, String
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class Holiday(Base, TimestampMixin):
    __tablename__ = "holidays"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    date: Mapped[date_] = mapped_column(Date, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    type: Mapped[str] = mapped_column(
        String(16), nullable=False, default="national"
    )  # national | company
