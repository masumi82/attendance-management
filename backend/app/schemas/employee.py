from __future__ import annotations

from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.employee import Role


class EmployeeCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=100)
    role: Role = Role.MEMBER
    department_id: UUID | None = None
    hire_date: date | None = None


class EmployeeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    role: Role | None = None
    department_id: UUID | None = None
    hire_date: date | None = None
    active: bool | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)


class EmployeeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    name: str
    role: Role
    department_id: UUID | None
    hire_date: date | None
    active: bool
