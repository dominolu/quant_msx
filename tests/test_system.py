from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.core.config import settings
from app.main import app
from app.services.scheduler_service import SchedulerService
from app.storage.db import SessionLocal, create_db_and_tables
from app.storage.models import SchedulerLockRecord


def test_healthz() -> None:
    client = TestClient(app)
    assert client.get("/healthz").json() == {"status": "ok"}


def test_dashboard() -> None:
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert "MSX 网格量化控制台" in response.text


def test_scheduler_single_runs_delegate_to_services() -> None:
    create_db_and_tables()
    with SessionLocal() as session:
        session.execute(delete(SchedulerLockRecord))
        session.commit()

    class GridStub:
        async def sync_and_check_running_grids(self) -> dict[str, int]:
            return {"checked": 1, "anomalies": 1}

    class AccountStub:
        async def snapshot_enabled_accounts(self) -> dict[str, int]:
            return {"attempted": 2, "succeeded": 2, "failed": 0}

    scheduler = SchedulerService(
        grid_service=GridStub(),  # type: ignore[arg-type]
        account_service=AccountStub(),  # type: ignore[arg-type]
    )

    import asyncio

    assert asyncio.run(scheduler.run_grid_health_sync_once()) == {"checked": 1, "anomalies": 1}
    assert asyncio.run(scheduler.run_account_balance_snapshot_once()) == {
        "attempted": 2,
        "succeeded": 2,
        "failed": 0,
    }
    assert scheduler.last_grid_sync_at is not None
    assert scheduler.last_account_snapshot_at is not None


def test_scheduler_status_endpoint() -> None:
    client = TestClient(app)
    response = client.get("/api/system/scheduler")

    assert response.status_code == 200
    assert "running" in response.json()
    assert "last_grid_error" in response.json()


def test_scheduler_disabled_does_not_start(monkeypatch) -> None:
    monkeypatch.setattr(settings, "scheduler_enabled", False)
    scheduler = SchedulerService()

    import asyncio

    asyncio.run(scheduler.start())
    assert scheduler.status()["running"] is False


def test_scheduler_start_stop_lifecycle(monkeypatch) -> None:
    monkeypatch.setattr(settings, "scheduler_enabled", True)
    monkeypatch.setattr(settings, "scheduler_initial_delay_seconds", 60.0)

    scheduler = SchedulerService()

    import asyncio

    async def scenario() -> None:
        await scheduler.start()
        assert scheduler.status()["running"] is True
        await scheduler.stop()
        assert scheduler.status()["running"] is False

    asyncio.run(scenario())


def test_scheduler_lock_prevents_duplicate_job() -> None:
    create_db_and_tables()
    with SessionLocal() as session:
        session.execute(delete(SchedulerLockRecord))
        session.commit()

    class GridStub:
        def __init__(self) -> None:
            self.calls = 0

        async def sync_and_check_running_grids(self) -> dict[str, int]:
            self.calls += 1
            return {"checked": self.calls, "anomalies": 0}

    import asyncio

    first_grid = GridStub()
    second_grid = GridStub()
    first = SchedulerService(grid_service=first_grid)  # type: ignore[arg-type]
    second = SchedulerService(grid_service=second_grid)  # type: ignore[arg-type]

    assert asyncio.run(first.run_grid_health_sync_once()) == {"checked": 1, "anomalies": 0}
    assert asyncio.run(second.run_grid_health_sync_once()) == {"checked": 0, "anomalies": 0}
    assert first_grid.calls == 1
    assert second_grid.calls == 0
