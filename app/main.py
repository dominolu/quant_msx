from fastapi import FastAPI

from app.api.routes import accounts, grids, system
from app.core.config import settings
from app.storage.db import create_db_and_tables
from app.web.routes import router as web_router
from app.web.static import mount_static


def create_app() -> FastAPI:
    create_db_and_tables()
    app = FastAPI(title=settings.app_name)
    mount_static(app)
    app.include_router(web_router)
    app.include_router(system.router)
    app.include_router(accounts.router)
    app.include_router(grids.router)
    return app


app = create_app()
