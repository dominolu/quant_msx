from fastapi import APIRouter

from app.core.config import settings
from app.services.scheduler_service import SchedulerService

router = APIRouter()
scheduler_service: SchedulerService | None = None


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
        "scheduler_enabled": settings.scheduler_enabled,
        "grid_health_sync_interval_seconds": str(settings.grid_health_sync_interval_seconds),
        "account_balance_snapshot_interval_seconds": str(
            settings.account_balance_snapshot_interval_seconds
        ),
    }


@router.get("/api/system/scheduler")
async def scheduler_status() -> dict[str, object]:
    if scheduler_service is None:
        return {
            "enabled": settings.scheduler_enabled,
            "running": False,
            "started_at": "",
            "last_grid_sync_at": "",
            "last_account_snapshot_at": "",
            "last_grid_error": "",
            "last_account_error": "",
        }
    return scheduler_service.status()
