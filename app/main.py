from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI

from app.api.routes import accounts, grids, orders, system
from app.core.config import settings
from app.services.scheduler_service import SchedulerService
from app.storage.db import create_db_and_tables
from app.web.routes import router as web_router
from app.web.static import mount_static

scheduler_service = SchedulerService()
system.scheduler_service = scheduler_service


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    await scheduler_service.start()
    try:
        yield
    finally:
        await scheduler_service.stop()


def create_app() -> FastAPI:
    create_db_and_tables()
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    mount_static(app)
    app.include_router(web_router)
    app.include_router(system.router)
    app.include_router(accounts.router)
    app.include_router(grids.router)
    app.include_router(orders.router)
    return app


app = create_app()
