"""Idempotent bootstrap seeds (e.g., ensure an initial admin exists)."""

from __future__ import annotations

import logging
import os

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.employee import Employee, Role

logger = logging.getLogger(__name__)


def ensure_initial_admin() -> None:
    email = os.environ.get("INITIAL_ADMIN_EMAIL")
    password = os.environ.get("INITIAL_ADMIN_PASSWORD")
    name = os.environ.get("INITIAL_ADMIN_NAME", "管理者")

    if not email or not password:
        logger.info("INITIAL_ADMIN_EMAIL / PASSWORD not set; skipping seed.")
        return

    with SessionLocal() as db:
        existing = db.execute(
            select(Employee).where(Employee.email == email.lower())
        ).scalar_one_or_none()
        if existing is not None:
            logger.info("Initial admin already exists: %s", existing.email)
            return
        db.add(
            Employee(
                email=email.lower(),
                hashed_password=hash_password(password),
                name=name,
                role=Role.ADMIN,
                active=True,
            )
        )
        db.commit()
        logger.info("Seeded initial admin: %s", email)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ensure_initial_admin()
