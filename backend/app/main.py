from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import (
    admin,
    attendance,
    auth,
    closings,
    employees,
    health,
    leaves,
    masters,
    shifts,
)
from app.api.v1 import requests as requests_api
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.jobs.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    setup_logging()
    settings = get_settings()
    if settings.APP_ENV != "test":
        start_scheduler()
    try:
        yield
    finally:
        stop_scheduler()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="勤怠管理システム API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.APP_ENV != "production" else None,
        redoc_url=None,
    )

    if settings.cors_origins_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins_list,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.include_router(health.router, prefix="/api")
    app.include_router(auth.router, prefix="/api")
    app.include_router(employees.router, prefix="/api")
    app.include_router(attendance.router, prefix="/api")
    app.include_router(requests_api.router, prefix="/api")
    app.include_router(requests_api.approvals_router, prefix="/api")
    app.include_router(admin.router, prefix="/api")
    app.include_router(leaves.router, prefix="/api")
    app.include_router(leaves.admin_router, prefix="/api")
    app.include_router(shifts.router, prefix="/api")
    app.include_router(shifts.admin_router, prefix="/api")
    app.include_router(shifts.emp_type_router, prefix="/api")
    app.include_router(masters.router, prefix="/api")
    app.include_router(masters.admin_dept_router, prefix="/api")
    app.include_router(masters.holidays_router, prefix="/api")
    app.include_router(masters.admin_holidays_router, prefix="/api")
    app.include_router(closings.router, prefix="/api")
    app.include_router(closings.exports_router, prefix="/api")

    return app


app = create_app()
