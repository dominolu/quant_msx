import asyncio

import httpx
import pytest
from sqlalchemy import delete

from app.core.config import settings
from app.domain.grid import GridCreateRequest, GridReconfigureRequest
from app.domain.orders import OrderCancelRequest, OrderSubmitRequest
from app.main import app
from app.services.order_service import OrderService
from app.services.grid_service import GridService
from app.storage.db import SessionLocal, create_db_and_tables
from app.storage.models import (
    GridEventRecord,
    GridFillRecord,
    GridOrderRecord,
    GridReconfigureRecord,
    GridStrategyRecord,
    TradingOrderRecord,
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
        session.execute(delete(TradingOrderRecord))
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
    orders_response = run(get(f"/api/contract-grids/{grid_id}/orders"))
    assert orders_response.status_code == 200
    assert len(orders_response.json()["items"]) == 2
    audit_response = run(get(f"/api/orders?source=grid&source_id={grid_id}"))
    assert audit_response.status_code == 200
    assert len(audit_response.json()["items"]) == 2

    delete_running_response = run(delete_http(f"/api/contract-grids/{grid_id}"))
    assert delete_running_response.status_code == 400

    pause_response = run(post(f"/api/contract-grids/{grid_id}/pause"))
    assert pause_response.status_code == 200
    assert pause_response.json()["grid"]["status"] == "paused"
    paused_orders_response = run(get(f"/api/contract-grids/{grid_id}/orders"))
    assert {item["status"] for item in paused_orders_response.json()["items"]} == {"canceled"}

    resume_response = run(post(f"/api/contract-grids/{grid_id}/resume"))
    assert resume_response.status_code == 200
    assert resume_response.json()["grid"]["status"] == "running"
    resumed_orders_response = run(get(f"/api/contract-grids/{grid_id}/orders"))
    assert len(resumed_orders_response.json()["items"]) == 4
    assert {item["role"] for item in resumed_orders_response.json()["items"]} == {
        "lower_buy",
        "upper_sell",
    }

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


def test_grid_start_places_only_current_pair_even_with_larger_open_limit() -> None:
    reset_grid_tables()
    payload = grid_payload("ADAUSDT")
    payload["max_open_orders_per_side"] = 5

    create_response = run(post("/api/contract-grids", payload))
    grid_id = create_response.json()["grid"]["id"]
    start_response = run(post(f"/api/contract-grids/{grid_id}/start"))

    assert start_response.status_code == 200
    assert start_response.json()["grid"]["current_round"] == 0
    orders_response = run(get(f"/api/contract-grids/{grid_id}/orders"))
    orders = orders_response.json()["items"]
    assert len(orders) == 2
    assert {order["role"] for order in orders} == {"lower_buy", "upper_sell"}
    assert {order["round_no"] for order in orders} == {0}


def test_grid_fill_advances_round_reprices_and_replaces_pair() -> None:
    reset_grid_tables()
    create_response = run(post("/api/contract-grids", grid_payload("DOGEUSDT")))
    grid_id = create_response.json()["grid"]["id"]
    run(post(f"/api/contract-grids/{grid_id}/start"))
    orders = run(get(f"/api/contract-grids/{grid_id}/orders")).json()["items"]
    lower_order = next(order for order in orders if order["role"] == "lower_buy")
    upper_order = next(order for order in orders if order["role"] == "upper_sell")

    fill_response = run(
        post(
            f"/api/contract-grids/{grid_id}/orders/{lower_order['id']}/fill",
            {
                "price": lower_order["price"],
                "qty": lower_order["qty"],
                "exchange_trade_id": "trade-1",
            },
        )
    )

    assert fill_response.status_code == 200
    grid = fill_response.json()["grid"]
    assert grid["current_round"] == 1
    assert grid["base_price"] == lower_order["price"]
    assert float(grid["grid_profit_usdt"].replace("+", "")) > 0
    assert float(grid["grid_profit_pct"].replace("%", "").replace("+", "")) > 0
    assert grid["pnl_updated_at"]
    updated_orders = run(get(f"/api/contract-grids/{grid_id}/orders")).json()["items"]
    assert len(updated_orders) == 4
    by_id = {order["id"]: order for order in updated_orders}
    assert by_id[lower_order["id"]]["status"] == "filled"
    assert by_id[upper_order["id"]]["status"] == "canceled"
    new_open = [
        order
        for order in updated_orders
        if order["status"] == "simulated" and order["round_no"] == 1
    ]
    assert len(new_open) == 2
    assert {order["role"] for order in new_open} == {"lower_buy", "upper_sell"}
    fills = run(get(f"/api/contract-grids/{grid_id}/fills")).json()["items"]
    assert len(fills) == 1
    assert fills[0]["exchange_trade_id"] == "trade-1"
    assert float(fills[0]["grid_profit_usdt"]) > 0


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


def test_order_api_simulated_submit_and_cancel() -> None:
    reset_grid_tables()
    response = run(
        post(
            "/api/orders",
            {
                "market": "futures",
                "symbol": "BTCUSDT",
                "side": "buy",
                "order_type": "limit",
                "price": "100",
                "qty": "0.1",
                "client_order_id": "manual-1",
            },
        )
    )
    assert response.status_code == 200
    order = response.json()
    assert order["status"] == "simulated"
    assert order["exchange_order_id"].startswith("sim-")

    cancel_response = run(
        post(
            "/api/orders/cancel",
            {
                "market": "futures",
                "symbol": "BTCUSDT",
                "order_id": order["exchange_order_id"],
            },
        )
    )
    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == "canceled"


def test_order_api_rejects_invalid_symbol() -> None:
    reset_grid_tables()
    response = run(
        post(
            "/api/orders",
            {
                "market": "futures",
                "symbol": "<script>",
                "side": "buy",
                "order_type": "limit",
                "price": "100",
                "qty": "0.1",
            },
        )
    )
    assert response.status_code == 422


def test_live_order_without_exchange_id_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    reset_grid_tables()
    monkeypatch.setattr(settings, "live_trading_enabled", True)

    class MissingOrderIdService(OrderService):
        async def _submit_live_order(self, request: OrderSubmitRequest) -> dict[str, object]:
            return {"code": 0, "data": {}}

    with pytest.raises(ValueError, match="exchange order id"):
        run(
            MissingOrderIdService().place_order(
                OrderSubmitRequest(
                    market="futures",
                    symbol="BTCUSDT",
                    side="buy",
                    order_type="limit",
                    price="100",
                    qty="0.1",
                )
            )
        )

    with SessionLocal() as session:
        row = session.query(TradingOrderRecord).one()
        assert row.status == "failed"
        assert row.exchange_order_id == ""


def test_cancel_failure_preserves_open_order(monkeypatch: pytest.MonkeyPatch) -> None:
    reset_grid_tables()
    monkeypatch.setattr(settings, "live_trading_enabled", True)
    with SessionLocal() as session:
        session.add(
            TradingOrderRecord(
                market="futures",
                symbol="BTCUSDT",
                side="buy",
                order_type="limit",
                price=100,
                qty=0.1,
                status="open",
                exchange_order_id="123",
                live=True,
            )
        )
        session.commit()

    class CancelFailureService(OrderService):
        async def _cancel_live_order(
            self,
            request: OrderCancelRequest,
            record: TradingOrderRecord,
        ) -> dict[str, object]:
            raise RuntimeError("exchange timeout")

    with pytest.raises(RuntimeError, match="exchange timeout"):
        run(
            CancelFailureService().cancel_order(
                OrderCancelRequest(market="futures", symbol="BTCUSDT", order_id="123")
            )
        )

    with SessionLocal() as session:
        row = session.query(TradingOrderRecord).one()
        assert row.status == "open"
        assert "cancel failed" in row.error_message


def test_grid_start_failure_compensates_submitted_orders() -> None:
    reset_grid_tables()

    class PartialFailureOrderService(OrderService):
        def __init__(self) -> None:
            super().__init__()
            self.cancel_called = False

        async def submit_grid_orders(
            self,
            *,
            grid_id: int,
            account_id: int | None,
            market: str,
            symbol: str,
            leverage: str,
            orders: list[dict[str, object]],
        ):
            first = orders[0]
            self._record_grid_order(
                grid_id=grid_id,
                exchange_order_id="sim-partial",
                client_order_id=str(first["client_order_id"]),
                side=str(first["side"]),
                price=self._to_float(first["price"]),
                qty=self._to_float(first["qty"]),
                status="simulated",
                role=str(first["role"]),
            )
            raise RuntimeError("second order failed")

        async def cancel_grid_open_orders(self, grid_id: int) -> int:
            self.cancel_called = True
            with SessionLocal() as session:
                rows = session.query(GridOrderRecord).filter(
                    GridOrderRecord.grid_id == grid_id,
                ).all()
                for row in rows:
                    row.status = "canceled"
                session.commit()
                return len(rows)

    order_service = PartialFailureOrderService()
    grid_service = GridService(order_service=order_service)
    create_result = run(grid_service.create_grid(GridCreateRequest(**grid_payload("XRPUSDT"))))

    with pytest.raises(RuntimeError, match="second order failed"):
        run(grid_service.start_grid(create_result.grid.id))

    assert order_service.cancel_called
    detail = grid_service.get_detail(create_result.grid.id)
    assert detail.grid.status == "error"
    assert {order.status for order in detail.orders} == {"canceled"}


def test_create_rejects_invalid_exchange() -> None:
    reset_grid_tables()
    payload = grid_payload()
    payload["exchange"] = "GATE"

    response = run(post("/api/contract-grids", payload))

    assert response.status_code == 422


def test_directional_grid_start_builds_initial_position_and_stop_flattens() -> None:
    reset_grid_tables()
    payload = grid_payload("BNBUSDT")
    payload["direction"] = "long_bias"
    create_response = run(post("/api/contract-grids", payload))
    grid_id = create_response.json()["grid"]["id"]

    start_response = run(post(f"/api/contract-grids/{grid_id}/start"))
    assert start_response.status_code == 200
    assert float(start_response.json()["grid"]["current_position_qty"]) > 0

    with SessionLocal() as session:
        market_orders = session.query(TradingOrderRecord).filter(
            TradingOrderRecord.source == "grid",
            TradingOrderRecord.source_id == grid_id,
            TradingOrderRecord.order_type == "market",
        ).all()
        assert len(market_orders) == 1
        assert market_orders[0].side == "buy"

    stop_response = run(post(f"/api/contract-grids/{grid_id}/stop"))
    assert stop_response.status_code == 200
    assert stop_response.json()["grid"]["current_position_qty"] == "0"

    with SessionLocal() as session:
        market_orders = session.query(TradingOrderRecord).filter(
            TradingOrderRecord.source == "grid",
            TradingOrderRecord.source_id == grid_id,
            TradingOrderRecord.order_type == "market",
        ).order_by(TradingOrderRecord.id).all()
        assert len(market_orders) == 2
        assert market_orders[-1].side == "sell"


def test_running_grid_reconfigure_cancels_and_replaces_current_pair() -> None:
    reset_grid_tables()
    create_response = run(post("/api/contract-grids", grid_payload("MATICUSDT")))
    grid_id = create_response.json()["grid"]["id"]
    run(post(f"/api/contract-grids/{grid_id}/start"))

    reconfigure_response = run(
        patch(
            f"/api/contract-grids/{grid_id}/params",
            {"grid_levels": "12", "lower_boundary": "88", "upper_boundary": "112"},
        )
    )

    assert reconfigure_response.status_code == 200
    meta = reconfigure_response.json()["reconfigure"]
    assert meta["cancelled_order_count"] == 2
    assert meta["submitted_order_count"] == 2
    orders = run(get(f"/api/contract-grids/{grid_id}/orders")).json()["items"]
    open_orders = [order for order in orders if order["status"] == "simulated"]
    assert len(open_orders) == 2


def test_duplicate_fill_is_ignored_by_trade_id() -> None:
    reset_grid_tables()
    create_response = run(post("/api/contract-grids", grid_payload("AVAXUSDT")))
    grid_id = create_response.json()["grid"]["id"]
    run(post(f"/api/contract-grids/{grid_id}/start"))
    order = run(get(f"/api/contract-grids/{grid_id}/orders")).json()["items"][0]
    payload = {"price": order["price"], "qty": order["qty"], "exchange_trade_id": "dup-trade"}

    first = run(post(f"/api/contract-grids/{grid_id}/orders/{order['id']}/fill", payload))
    second = run(post(f"/api/contract-grids/{grid_id}/orders/{order['id']}/fill", payload))

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["message"] == "duplicate_fill_ignored"
    fills = run(get(f"/api/contract-grids/{grid_id}/fills")).json()["items"]
    assert len(fills) == 1


def test_grid_sync_updates_position_pnl_and_rest_counter() -> None:
    reset_grid_tables()

    class SyncOrderService(OrderService):
        async def get_open_orders(
            self,
            market: str,
            symbol: str | None = None,
            account_id: int | None = None,
        ):
            return {"data": []}

        async def get_history_orders(
            self,
            market: str,
            symbol: str | None = None,
            account_id: int | None = None,
        ):
            return {"data": []}

        async def get_trades(
            self,
            market: str,
            symbol: str | None = None,
            account_id: int | None = None,
        ):
            return {"data": []}

        async def get_positions(self, account_id: int | None = None, symbol: str | None = None):
            return {
                "data": [
                    {
                        "symbol": symbol,
                        "qty": "0.25",
                        "realizedPnl": "1.5",
                        "unrealizedPnl": "2.5",
                        "fundingFee": "-0.1",
                        "markPrice": "101",
                    }
                ]
            }

    service = GridService(order_service=SyncOrderService())
    create_result = run(service.create_grid(GridCreateRequest(**grid_payload("LINKUSDT"))))
    result = run(service.sync_grid_from_rest(create_result.grid.id))
    grid = result.items[0]

    assert grid.current_position_qty == "0.25"
    assert grid.realized_pnl_usdt == "+1.50"
    assert grid.unrealized_pnl_usdt == "+2.50"
    assert grid.funding_fee_usdt == "-0.10"
    assert grid.rest_sync_count == 1


def test_start_initial_position_failure_marks_grid_error() -> None:
    reset_grid_tables()

    class InitialPositionFailureService(OrderService):
        async def place_order(self, request: OrderSubmitRequest):
            if request.order_type == "market":
                raise RuntimeError("market order rejected")
            return await super().place_order(request)

    payload = grid_payload("ATOMUSDT")
    payload["direction"] = "long_bias"
    service = GridService(order_service=InitialPositionFailureService())
    create_result = run(service.create_grid(GridCreateRequest(**payload)))

    with pytest.raises(RuntimeError, match="market order rejected"):
        run(service.start_grid(create_result.grid.id))

    detail = service.get_detail(create_result.grid.id)
    assert detail.grid.status == "error"
    assert "启动失败" in detail.grid.health


def test_running_reconfigure_failure_marks_grid_and_record_failed() -> None:
    reset_grid_tables()

    class ReconfigureFailureService(OrderService):
        async def submit_grid_orders(
            self,
            *,
            grid_id: int,
            account_id: int | None,
            market: str,
            symbol: str,
            leverage: str,
            orders: list[dict[str, object]],
        ):
            existing = self.list_orders(source="grid", source_id=grid_id).items
            if existing:
                raise RuntimeError("exchange unavailable")
            return await super().submit_grid_orders(
                grid_id=grid_id,
                account_id=account_id,
                market=market,
                symbol=symbol,
                leverage=leverage,
                orders=orders,
            )

    service = GridService(order_service=ReconfigureFailureService())
    create_result = run(service.create_grid(GridCreateRequest(**grid_payload("NEARUSDT"))))
    run(service.start_grid(create_result.grid.id))

    with pytest.raises(RuntimeError, match="exchange unavailable"):
        run(
            service.reconfigure_grid(
                create_result.grid.id,
                GridReconfigureRequest(
                    grid_levels="12",
                    lower_boundary="88",
                    upper_boundary="112",
                ),
            )
        )

    detail = service.get_detail(create_result.grid.id)
    assert detail.grid.status == "error"
    with SessionLocal() as session:
        record = session.query(GridReconfigureRecord).one()
        assert record.status == "failed"
        assert "exchange unavailable" in record.error_message


def test_rest_sync_filled_order_uses_fill_flow_and_replaces_pair() -> None:
    reset_grid_tables()

    class FilledHistoryService(OrderService):
        async def get_open_orders(
            self,
            market: str,
            symbol: str | None = None,
            account_id: int | None = None,
        ):
            return {"data": []}

        async def get_history_orders(
            self,
            market: str,
            symbol: str | None = None,
            account_id: int | None = None,
        ):
            with SessionLocal() as session:
                order = session.query(GridOrderRecord).order_by(GridOrderRecord.id).first()
                assert order is not None
                return {
                    "data": [
                        {
                            "orderId": order.exchange_order_id,
                            "status": "filled",
                            "filledQty": str(order.qty),
                            "avgFillPrice": str(order.price),
                            "fee": "0",
                        }
                    ]
                }

        async def get_trades(
            self,
            market: str,
            symbol: str | None = None,
            account_id: int | None = None,
        ):
            return {"data": []}

        async def get_positions(self, account_id: int | None = None, symbol: str | None = None):
            return {"data": [{"symbol": symbol, "qty": "0", "markPrice": "100"}]}

    service = GridService(order_service=FilledHistoryService())
    create_result = run(service.create_grid(GridCreateRequest(**grid_payload("UNIUSDT"))))
    run(service.start_grid(create_result.grid.id))

    result = run(service.sync_grid_from_rest(create_result.grid.id))

    grid = result.items[0]
    assert grid.current_round == 1
    detail = service.get_detail(create_result.grid.id)
    assert len(detail.fills) == 1
    assert len([order for order in detail.orders if order.status == "simulated"]) == 2


def test_manual_fill_endpoint_forbidden_outside_demo(monkeypatch: pytest.MonkeyPatch) -> None:
    reset_grid_tables()
    monkeypatch.setattr(settings, "live_trading_enabled", True)
    monkeypatch.setattr(settings, "grid_demo_mode", False)

    response = run(
        post(
            "/api/contract-grids/1/orders/1/fill",
            {"price": "1", "qty": "1", "exchange_trade_id": "blocked"},
        )
    )

    assert response.status_code == 403
