from fastapi import APIRouter

from app.core.config import settings

router = APIRouter()


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz")
async def readyz() -> dict[str, str]:
    return {"status": "ready"}


@router.get("/api/system/info")
async def system_info() -> dict[str, str | bool]:
    return {
        "app_name": settings.app_name,
        "app_env": settings.app_env,
        "live_trading_enabled": settings.live_trading_enabled,
        "grid_demo_mode": settings.grid_demo_mode,
    }
