from fastapi import FastAPI

from app.api.routes import system
from app.core.config import settings
from app.web.routes import router as web_router
from app.web.static import mount_static


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name)
    mount_static(app)
    app.include_router(web_router)
    app.include_router(system.router)
    return app


app = create_app()
