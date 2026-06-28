import asyncio

import httpx
import pytest
from sqlalchemy import delete

from app.main import app
from app.services.grid_service import GridService
from app.storage.db import SessionLocal, create_db_and_tables
from app.storage.models import (
    GridEventRecord,
    GridFillRecord,
    GridOrderRecord,
    GridReconfigureRecord,
    GridStrategyRecord,
)

transport = httpx.ASGITransport(app=app)


def run(coro):
    return asyncio.run(coro)


def reset_grid_tables() -> None:
    create_db_and_tables()
    with SessionLocal() as session:
        session.execute(delete(GridEventRecord))
        session.execute(delete(GridFillRecord))
        session.execute(delete(GridOrderRecord))
        session.execute(delete(GridReconfigureRecord))
        session.execute(delete(GridStrategyRecord))
        session.commit()


async def post(path: str, payload: dict[str, object] | None = None) -> httpx.Response:
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.post(path, json=payload)


async def get(path: str) -> httpx.Response:
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.get(path)


async def patch(path: str, payload: dict[str, object] | None = None) -> httpx.Response:
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.patch(path, json=payload)


async def delete_http(path: str) -> httpx.Response:
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.delete(path)


def grid_payload(symbol: str = "BTCUSDT") -> dict[str, object]:
    return {
        "name": f"{symbol} neutral grid",
        "exchange": "MSX",
        "market": "futures",
        "symbol": symbol,
        "direction": "neutral",
        "leverage": "2",
        "margin_usdt": "100",
        "spacing_mode": "geometric",
        "grid_levels": "10",
        "stop_loss_price": "90",
        "take_profit_price": "110",
        "base_price": "100",
    }


def test_compute_grid_orders_geometric() -> None:
    result = GridService.compute_grid_orders(
        P_lower=90,
        P_upper=110,
        N=10,
        M=100,
        L=2,
        P_current=100,
        spacing_mode="geometric",
    )

    assert result["order_qty"] > 0
    assert result["buy_price"] < 100
    assert result["sell_price"] > 100


def test_grid_api_lifecycle_and_reconfigure() -> None:
    reset_grid_tables()

    create_response = run(post("/api/contract-grids", grid_payload()))
    assert create_response.status_code == 200
    grid = create_response.json()["grid"]
    grid_id = grid["id"]
    assert grid["status"] == "draft"
    assert grid["lower_order_price"] != "0"

    duplicate_response = run(post("/api/contract-grids", grid_payload()))
    assert duplicate_response.status_code == 400

    reconfigure_response = run(
        patch(
            f"/api/contract-grids/{grid_id}/params",
            {"grid_levels": "12", "lower_boundary": "88", "upper_boundary": "112"},
        )
    )
    assert reconfigure_response.status_code == 200
    assert reconfigure_response.json()["reconfigure"]["version"] == 1

    start_response = run(post(f"/api/contract-grids/{grid_id}/start"))
    assert start_response.status_code == 200
    assert start_response.json()["grid"]["status"] == "running"

    delete_running_response = run(delete_http(f"/api/contract-grids/{grid_id}"))
    assert delete_running_response.status_code == 400

    pause_response = run(post(f"/api/contract-grids/{grid_id}/pause"))
    assert pause_response.status_code == 200
    assert pause_response.json()["grid"]["status"] == "paused"

    resume_response = run(post(f"/api/contract-grids/{grid_id}/resume"))
    assert resume_response.status_code == 200
    assert resume_response.json()["grid"]["status"] == "running"

    stop_response = run(post(f"/api/contract-grids/{grid_id}/stop"))
    assert stop_response.status_code == 200
    assert stop_response.json()["grid"]["status"] == "stopped"

    detail_response = run(get(f"/api/contract-grids/{grid_id}"))
    assert detail_response.status_code == 200
    assert detail_response.json()["events"]

    delete_response = run(delete_http(f"/api/contract-grids/{grid_id}"))
    assert delete_response.status_code == 200
    assert delete_response.json()["items"] == []


def test_grid_state_machine_blocks_invalid_transitions_and_duplicate_running() -> None:
    reset_grid_tables()

    create_response = run(post("/api/contract-grids", grid_payload()))
    grid_id = create_response.json()["grid"]["id"]

    pause_draft_response = run(post(f"/api/contract-grids/{grid_id}/pause"))
    assert pause_draft_response.status_code == 400

    start_response = run(post(f"/api/contract-grids/{grid_id}/start"))
    assert start_response.status_code == 200

    stop_response = run(post(f"/api/contract-grids/{grid_id}/stop"))
    assert stop_response.status_code == 200

    second_create_response = run(post("/api/contract-grids", grid_payload()))
    assert second_create_response.status_code == 200
    second_grid_id = second_create_response.json()["grid"]["id"]
    second_start_response = run(post(f"/api/contract-grids/{second_grid_id}/start"))
    assert second_start_response.status_code == 200

    restart_stopped_response = run(post(f"/api/contract-grids/{grid_id}/start"))
    assert restart_stopped_response.status_code == 400

    list_response = run(get("/api/contract-grids"))
    running = [item for item in list_response.json()["items"] if item["status"] == "running"]
    assert len(running) == 1
    assert running[0]["id"] == second_grid_id


def test_grid_create_rejects_unsafe_or_invalid_params() -> None:
    reset_grid_tables()

    invalid_symbol = grid_payload("<script>")
    assert run(post("/api/contract-grids", invalid_symbol)).status_code == 400

    invalid_spacing = grid_payload("ETHUSDT")
    invalid_spacing["spacing_mode"] = "whatever"
    assert run(post("/api/contract-grids", invalid_spacing)).status_code == 400

    invalid_qty = grid_payload("SOLUSDT")
    invalid_qty["order_qty"] = "-1"
    assert run(post("/api/contract-grids", invalid_qty)).status_code == 400


def test_grid_reconfigure_updates_target_position_for_directional_grid() -> None:
    reset_grid_tables()
    payload = grid_payload("ETHUSDT")
    payload["direction"] = "long_bias"

    create_response = run(post("/api/contract-grids", payload))
    grid_id = create_response.json()["grid"]["id"]
    original_target = create_response.json()["grid"]["current_position_qty"]
    assert original_target == "0"

    reconfigure_response = run(
        patch(
            f"/api/contract-grids/{grid_id}/params",
            {"grid_levels": "20", "margin_usdt": "200"},
        )
    )

    assert reconfigure_response.status_code == 200
    reconfigure = reconfigure_response.json()["reconfigure"]
    assert float(reconfigure["target_net_position"]) > 0


def test_grid_subresources_return_404_for_missing_grid() -> None:
    reset_grid_tables()

    assert run(get("/api/contract-grids/999/orders")).status_code == 404
    assert run(get("/api/contract-grids/999/fills")).status_code == 404
    assert run(get("/api/contract-grids/999/events")).status_code == 404


def test_create_rejects_invalid_exchange() -> None:
    reset_grid_tables()
    payload = grid_payload()
    payload["exchange"] = "GATE"

    response = run(post("/api/contract-grids", payload))

    assert response.status_code == 422
