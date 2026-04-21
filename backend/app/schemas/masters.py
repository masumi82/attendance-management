from __future__ import annotations

from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DepartmentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    code: str | None = Field(default=None, max_length=50)


class DepartmentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    code: str | None = Field(default=None, max_length=50)


class DepartmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    code: str | None


class HolidayCreate(BaseModel):
    date: date
    name: str = Field(min_length=1, max_length=100)
    type: Literal["national", "company"] = "national"


class HolidayOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    date: date
    name: str
    type: str
