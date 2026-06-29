from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta

from app.core.config import settings
from app.services.exchange_account_service import ExchangeAccountService
from app.services.grid_service import GridService
from app.storage.db import SessionLocal
from app.storage.models import SchedulerLockRecord

logger = logging.getLogger(__name__)


class SchedulerService:
    """Small in-process scheduler for operational sync jobs."""

    def __init__(
        self,
        *,
        grid_service: GridService | None = None,
        account_service: ExchangeAccountService | None = None,
    ) -> None:
        self.grid_service = grid_service or GridService()
        self.account_service = account_service or ExchangeAccountService()
        self._tasks: list[asyncio.Task[None]] = []
        self.owner = f"{os.getpid()}-{uuid.uuid4().hex[:8]}"
        self.started_at: datetime | None = None
        self.last_grid_sync_at: datetime | None = None
        self.last_account_snapshot_at: datetime | None = None
        self.last_grid_error: str = ""
        self.last_account_error: str = ""

    async def start(self) -> None:
        if not settings.scheduler_enabled:
            return
        if self._tasks:
            return
        self.started_at = datetime.utcnow()
        self._tasks = [
            asyncio.create_task(
                self._run_loop(
                    name="grid_health_sync",
                    interval_seconds=settings.grid_health_sync_interval_seconds,
                    initial_delay_seconds=settings.scheduler_initial_delay_seconds,
                    job=self.run_grid_health_sync_once,
                    error_attr="last_grid_error",
                )
            ),
            asyncio.create_task(
                self._run_loop(
                    name="account_balance_snapshot",
                    interval_seconds=settings.account_balance_snapshot_interval_seconds,
                    initial_delay_seconds=settings.scheduler_initial_delay_seconds,
                    job=self.run_account_balance_snapshot_once,
                    error_attr="last_account_error",
                )
            ),
        ]

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task
        self._tasks = []

    async def run_grid_health_sync_once(self) -> dict[str, int]:
        if not self._acquire_lock("grid_health_sync"):
            return {"checked": 0, "anomalies": 0}
        result = await self.grid_service.sync_and_check_running_grids()
        self.last_grid_sync_at = datetime.utcnow()
        self.last_grid_error = ""
        return result

    async def run_account_balance_snapshot_once(self) -> dict[str, int]:
        if not self._acquire_lock("account_balance_snapshot"):
            return {"attempted": 0, "succeeded": 0, "failed": 0}
        result = await self.account_service.snapshot_enabled_accounts()
        self.last_account_snapshot_at = datetime.utcnow()
        self.last_account_error = ""
        return result

    async def _run_loop(
        self,
        *,
        name: str,
        interval_seconds: float,
        initial_delay_seconds: float,
        job: Callable[[], Awaitable[dict[str, int]]],
        error_attr: str,
    ) -> None:
        interval = max(float(interval_seconds), 1.0)
        initial_delay = max(float(initial_delay_seconds), 0.0)
        if initial_delay:
            await asyncio.sleep(initial_delay)
        while True:
            try:
                result = await job()
                logger.info("scheduler job %s completed: %s", name, result)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                setattr(self, error_attr, f"{type(exc).__name__}: {exc}")
                logger.exception("scheduler job %s failed", name)
            await asyncio.sleep(interval)

    def _acquire_lock(self, name: str) -> bool:
        now = datetime.utcnow()
        locked_until = now + timedelta(seconds=max(settings.scheduler_lock_ttl_seconds, 1.0))
        with SessionLocal() as session:
            row = session.get(SchedulerLockRecord, name)
            if row is not None and row.locked_until > now and row.owner != self.owner:
                return False
            if row is None:
                row = SchedulerLockRecord(
                    name=name,
                    owner=self.owner,
                    locked_until=locked_until,
                    updated_at=now,
                )
                session.add(row)
            else:
                row.owner = self.owner
                row.locked_until = locked_until
                row.updated_at = now
            session.commit()
            return True

    def status(self) -> dict[str, object]:
        return {
            "enabled": settings.scheduler_enabled,
            "running": bool(self._tasks),
            "owner": self.owner,
            "started_at": self.started_at.isoformat(timespec="seconds") if self.started_at else "",
            "last_grid_sync_at": (
                self.last_grid_sync_at.isoformat(timespec="seconds")
                if self.last_grid_sync_at
                else ""
            ),
            "last_account_snapshot_at": (
                self.last_account_snapshot_at.isoformat(timespec="seconds")
                if self.last_account_snapshot_at
                else ""
            ),
            "grid_health_sync_interval_seconds": settings.grid_health_sync_interval_seconds,
            "account_balance_snapshot_interval_seconds": (
                settings.account_balance_snapshot_interval_seconds
            ),
            "scheduler_initial_delay_seconds": settings.scheduler_initial_delay_seconds,
            "scheduler_lock_ttl_seconds": settings.scheduler_lock_ttl_seconds,
            "last_grid_error": self.last_grid_error,
            "last_account_error": self.last_account_error,
        }
