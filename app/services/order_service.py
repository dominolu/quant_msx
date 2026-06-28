from __future__ import annotations

import json
import math
import re
from decimal import Decimal, InvalidOperation, ROUND_DOWN
from typing import Any

from sqlalchemy import desc, select

from app.broker.commands import (
    CancelFuturesOrderRequest,
    CancelSpotOrderRequest,
    FuturesOrderRequest,
    SpotOrderRequest,
)
from app.broker.msx import MsxBroker
from app.broker.msx_rest import MsxRestClient
from app.core.config import settings
from app.domain.orders import OrderCancelRequest, OrderListView, OrderSubmitRequest, OrderView
from app.services.account_credentials import AccountCredentialService
from app.storage.db import SessionLocal
from app.storage.models import (
    ExchangeAccountRecord,
    GridOrderRecord,
    TradingOrderRecord,
    utc_now,
)


OPEN_ORDER_STATUSES = {"open", "partially_filled", "simulated"}
SYMBOL_PATTERN = re.compile(r"^[A-Z0-9_/-]{2,40}$")
MIN_ORDER_NOTIONAL_USDT = Decimal("1")
ORDER_QUANT = Decimal("0.00000001")


class OrderService:
    """Unified order boundary for strategy code.

    The service records every order intent. When live trading is disabled it
    creates simulated open orders only; live MSX calls are made exclusively when
    the global live switch is enabled.
    """

    def __init__(
        self,
        *,
        credential_service: AccountCredentialService | None = None,
        broker_factory: object | None = None,
    ) -> None:
        self.credential_service = credential_service or AccountCredentialService()
        self.broker_factory = broker_factory

    async def place_order(self, request: OrderSubmitRequest) -> OrderView:
        self._validate_submit(request)
        now = utc_now()
        live = settings.live_trading_enabled
        record = TradingOrderRecord(
            account_id=request.account_id,
            source=request.source,
            source_id=request.source_id,
            market=request.market,
            symbol=request.symbol,
            side=request.side,
            order_type=request.order_type,
            price=self._to_float(request.price),
            qty=self._to_float(request.qty),
            status="pending",
            client_order_id=request.client_order_id,
            live=live,
            request_json=json.dumps(request.model_dump(), sort_keys=True),
            created_at=now,
            updated_at=now,
        )
        with SessionLocal() as session:
            session.add(record)
            session.commit()
            session.refresh(record)
            order_id = record.id

        if not live:
            return self._mark_order_result(
                order_id,
                status="simulated",
                exchange_order_id=f"sim-{order_id}",
                response={"simulated": True},
            )

        try:
            response = await self._submit_live_order(request)
            exchange_order_id = self._extract_order_id(response)
            if not exchange_order_id:
                raise ValueError("live order response did not include exchange order id")
            return self._mark_order_result(
                order_id,
                status="open",
                exchange_order_id=exchange_order_id,
                response=response,
            )
        except Exception as exc:
            self._mark_order_result(order_id, status="failed", error_message=str(exc))
            raise

    async def cancel_order(self, request: OrderCancelRequest) -> OrderView:
        record = self._get_order_for_cancel(request.order_id)
        if record.status not in OPEN_ORDER_STATUSES:
            raise ValueError(f"order is not open: {record.status}")

        if not settings.live_trading_enabled or record.exchange_order_id.startswith("sim-"):
            return self._mark_order_result(
                record.id,
                status="canceled",
                response={"simulated": True, "cancelled": True},
            )

        try:
            response = await self._cancel_live_order(request, record)
            return self._mark_order_result(record.id, status="canceled", response=response)
        except Exception as exc:
            self._record_order_error(record.id, f"cancel failed: {exc}")
            raise

    def list_orders(
        self,
        *,
        source: str | None = None,
        source_id: int | None = None,
        status: str | None = None,
        limit: int | None = None,
    ) -> OrderListView:
        with SessionLocal() as session:
            stmt = select(TradingOrderRecord).order_by(desc(TradingOrderRecord.updated_at))
            if source:
                stmt = stmt.where(TradingOrderRecord.source == source)
            if source_id is not None:
                stmt = stmt.where(TradingOrderRecord.source_id == source_id)
            if status:
                stmt = stmt.where(TradingOrderRecord.status == status)
            if limit is not None:
                stmt = stmt.limit(limit)
            rows = session.scalars(stmt).all()
        return OrderListView(items=[self._to_view(row) for row in rows])

    async def submit_grid_orders(
        self,
        *,
        grid_id: int,
        account_id: int | None,
        market: str,
        symbol: str,
        leverage: str,
        orders: list[dict[str, object]],
    ) -> list[GridOrderRecord]:
        submitted: list[GridOrderRecord] = []
        for item in orders:
            side = str(item["side"])
            price = self._normalize_decimal_string(item["price"])
            qty = self._normalize_decimal_string(item["qty"])
            if Decimal(price) * Decimal(qty) < MIN_ORDER_NOTIONAL_USDT:
                raise ValueError("grid order notional must be at least 1 USDT")
            client_order_id = str(item["client_order_id"])
            round_no = int(item.get("round_no") or 0)
            paired_open_order_id = item.get("paired_open_order_id")
            trading_order = await self.place_order(
                OrderSubmitRequest(
                    account_id=account_id,
                    source="grid",
                    source_id=grid_id,
                    market=market,  # type: ignore[arg-type]
                    symbol=symbol,
                    side=side,  # type: ignore[arg-type]
                    order_type="limit",
                    price=price,
                    qty=qty,
                    leverage=leverage,
                    client_order_id=client_order_id,
                )
            )
            submitted.append(
                self._record_grid_order(
                    grid_id=grid_id,
                    exchange_order_id=trading_order.exchange_order_id,
                    client_order_id=client_order_id,
                    side=side,
                    price=self._to_float(price),
                    qty=self._to_float(qty),
                    status=trading_order.status,
                    role=str(item.get("role") or "grid"),
                    round_no=round_no,
                    paired_open_order_id=(
                        int(paired_open_order_id)
                        if isinstance(paired_open_order_id, int | str)
                        and str(paired_open_order_id).isdigit()
                        else None
                    ),
                )
            )
        return submitted

    async def cancel_grid_open_orders(self, grid_id: int) -> int:
        with SessionLocal() as session:
            rows = session.scalars(
                select(GridOrderRecord).where(
                    GridOrderRecord.grid_id == grid_id,
                    GridOrderRecord.status.in_(tuple(OPEN_ORDER_STATUSES)),
                )
            ).all()

        cancelled = 0
        errors: list[str] = []
        for row in rows:
            try:
                await self.cancel_order(
                    OrderCancelRequest(
                        market="futures",
                        symbol="",
                        order_id=row.exchange_order_id,
                    )
                )
            except Exception as exc:
                errors.append(f"{row.exchange_order_id}: {exc}")
                continue
            else:
                self._mark_grid_order_status(row.id, "canceled")
                cancelled += 1
        if errors:
            raise ValueError("failed to cancel grid orders: " + "; ".join(errors))
        return cancelled

    async def get_open_orders(
        self,
        market: str,
        symbol: str | None = None,
        account_id: int | None = None,
    ) -> Any:
        broker = self._broker(account_id)
        try:
            return await broker.orders.get_open_orders(market, symbol=symbol)
        finally:
            await broker.close()

    async def get_history_orders(
        self,
        market: str,
        symbol: str | None = None,
        account_id: int | None = None,
    ) -> Any:
        async with self._rest_client(account_id) as client:
            if market == "spot":
                return await client.get_spot_history_orders(symbol=symbol)
            if market == "futures":
                return await client.get_futures_order_history(symbol=symbol)
        raise ValueError(f"unsupported market: {market}")

    async def get_trades(
        self,
        market: str,
        symbol: str | None = None,
        account_id: int | None = None,
    ) -> Any:
        async with self._rest_client(account_id) as client:
            if market == "spot":
                return await client.get_spot_trades(symbol=symbol)
            if market == "futures":
                return await client.get_futures_entrust_history(symbol=symbol)
        raise ValueError(f"unsupported market: {market}")

    async def get_positions(self, account_id: int | None = None, symbol: str | None = None) -> Any:
        broker = self._broker(account_id)
        try:
            return await broker.account.get_positions(symbol=symbol)
        finally:
            await broker.close()

    async def _submit_live_order(self, request: OrderSubmitRequest) -> Any:
        broker = self._broker(request.account_id)
        try:
            if request.market == "spot":
                return await broker.orders.create(
                    SpotOrderRequest(
                        symbol=request.symbol,
                        side=request.side,
                        type=request.order_type,
                        quantity=request.qty,
                        price=request.price if request.order_type == "limit" else None,
                        client_oid=request.client_order_id or None,
                    )
                )
            return await broker.orders.create(
                FuturesOrderRequest(
                    symbol=request.symbol,
                    co_type=1,
                    order_type=1 if request.order_type == "limit" else 2,
                    open_type=2 if request.reduce_only else 1,
                    side=1 if request.side == "buy" else 2,
                    price=request.price if request.order_type == "limit" else None,
                    vol=request.qty,
                    leverage=request.leverage,
                )
            )
        finally:
            await broker.close()

    async def _cancel_live_order(
        self,
        request: OrderCancelRequest,
        record: TradingOrderRecord,
    ) -> Any:
        broker = self._broker(request.account_id or record.account_id)
        try:
            if record.market == "spot":
                return await broker.orders.cancel(
                    CancelSpotOrderRequest(
                        symbol=request.symbol or record.symbol,
                        order_id=record.exchange_order_id,
                    )
                )
            return await broker.orders.cancel(
                CancelFuturesOrderRequest(order_id=int(record.exchange_order_id))
            )
        finally:
            await broker.close()

    def _broker(self, account_id: int | None) -> MsxBroker:
        return MsxBroker(rest=self._rest_client(account_id))

    def _rest_client(self, account_id: int | None) -> MsxRestClient:
        if account_id is None:
            return MsxRestClient()
        with SessionLocal() as session:
            account = session.get(ExchangeAccountRecord, account_id)
            if account is None:
                raise ValueError("account not found")
            if not account.enabled or account.status == "disabled":
                raise ValueError("account is disabled")
            credentials = self.credential_service.decrypt(account.credentials_encrypted)
        return MsxRestClient(
            api_key=str(credentials.get("api_key") or ""),
            secret_key=str(credentials.get("api_secret") or ""),
        )

    def _get_order_for_cancel(self, order_id: str) -> TradingOrderRecord:
        with SessionLocal() as session:
            row = session.scalar(
                select(TradingOrderRecord).where(
                    TradingOrderRecord.exchange_order_id == order_id
                )
            )
            if row is None and order_id.isdigit():
                row = session.get(TradingOrderRecord, int(order_id))
            if row is None:
                raise ValueError("order not found")
            session.expunge(row)
            return row

    def _record_order_error(self, order_id: int, error_message: str) -> OrderView:
        with SessionLocal() as session:
            row = session.get(TradingOrderRecord, order_id)
            if row is None:
                raise ValueError("order not found")
            row.error_message = error_message
            row.updated_at = utc_now()
            session.commit()
            session.refresh(row)
            return self._to_view(row)

    def _record_grid_order(
        self,
        *,
        grid_id: int,
        exchange_order_id: str,
        client_order_id: str,
        side: str,
        price: float,
        qty: float,
        status: str,
        role: str,
        round_no: int = 0,
        paired_open_order_id: int | None = None,
    ) -> GridOrderRecord:
        now = utc_now()
        row = GridOrderRecord(
            grid_id=grid_id,
            round_no=round_no,
            exchange_order_id=exchange_order_id,
            client_order_id=client_order_id,
            side=side,
            price=price,
            qty=qty,
            filled_qty=0.0,
            avg_fill_price=0.0,
            fee_usdt=0.0,
            status=status,
            role=role,
            paired_open_order_id=paired_open_order_id,
            submitted_at=now,
            updated_at=now,
        )
        with SessionLocal() as session:
            session.add(row)
            session.commit()
            session.refresh(row)
            session.expunge(row)
        return row

    def _mark_grid_order_status(self, grid_order_id: int, status: str) -> None:
        with SessionLocal() as session:
            row = session.get(GridOrderRecord, grid_order_id)
            if row is not None:
                row.status = status
                row.updated_at = utc_now()
            session.commit()

    def _mark_order_result(
        self,
        order_id: int,
        *,
        status: str,
        exchange_order_id: str | None = None,
        response: Any | None = None,
        error_message: str = "",
    ) -> OrderView:
        with SessionLocal() as session:
            row = session.get(TradingOrderRecord, order_id)
            if row is None:
                raise ValueError("order not found")
            row.status = status
            if exchange_order_id is not None:
                row.exchange_order_id = exchange_order_id
            if response is not None:
                row.response_json = json.dumps(response, sort_keys=True, default=str)
            row.error_message = error_message
            row.updated_at = utc_now()
            session.commit()
            session.refresh(row)
            return self._to_view(row)

    def _validate_submit(self, request: OrderSubmitRequest) -> None:
        if request.market not in {"spot", "futures"}:
            raise ValueError("market must be spot or futures")
        if request.side not in {"buy", "sell"}:
            raise ValueError("side must be buy or sell")
        if request.order_type not in {"limit", "market"}:
            raise ValueError("order_type must be limit or market")
        if not SYMBOL_PATTERN.fullmatch(request.symbol):
            raise ValueError("symbol must use 2-40 uppercase letters, digits, _, /, or -")
        if self._to_float(request.qty) <= 0:
            raise ValueError("qty must be greater than 0")
        if request.order_type == "limit" and self._to_float(request.price) <= 0:
            raise ValueError("limit price must be greater than 0")
        if self._to_float(request.leverage) <= 0:
            raise ValueError("leverage must be greater than 0")
        if len(request.source) > 32:
            raise ValueError("source must be 32 characters or fewer")
        if len(request.client_order_id) > 128:
            raise ValueError("client_order_id must be 128 characters or fewer")

    @staticmethod
    def _normalize_decimal_string(value: object) -> str:
        try:
            parsed = Decimal(str(value))
        except (InvalidOperation, ValueError):
            raise ValueError("order price and qty must be valid decimals") from None
        if not parsed.is_finite() or parsed <= 0:
            raise ValueError("order price and qty must be greater than 0")
        normalized = parsed.quantize(ORDER_QUANT, rounding=ROUND_DOWN).normalize()
        text = format(normalized, "f")
        return text.rstrip("0").rstrip(".") if "." in text else text

    @staticmethod
    def _extract_order_id(response: Any) -> str:
        data = response.get("data") if isinstance(response, dict) else response
        if isinstance(data, dict):
            for key in ("orderId", "order_id", "id"):
                if data.get(key) is not None:
                    return str(data[key])
        if isinstance(data, list) and data:
            first = data[0]
            if isinstance(first, dict):
                return OrderService._extract_order_id({"data": first})
        return ""

    @staticmethod
    def _to_view(row: TradingOrderRecord) -> OrderView:
        return OrderView(
            id=row.id,
            account_id=row.account_id,
            source=row.source,
            source_id=row.source_id,
            market=row.market,
            symbol=row.symbol,
            side=row.side,
            order_type=row.order_type,
            price=OrderService._fmt(row.price),
            qty=OrderService._fmt(row.qty),
            filled_qty=OrderService._fmt(row.filled_qty),
            avg_fill_price=OrderService._fmt(row.avg_fill_price),
            status=row.status,
            client_order_id=row.client_order_id,
            exchange_order_id=row.exchange_order_id,
            live=row.live,
            error_message=row.error_message,
            raw_response=OrderService._load_json(row.response_json),
            created_at=row.created_at.isoformat(timespec="seconds"),
            updated_at=row.updated_at.isoformat(timespec="seconds"),
        )

    @staticmethod
    def _load_json(raw: str) -> dict[str, object]:
        try:
            value = json.loads(raw or "{}")
        except json.JSONDecodeError:
            return {}
        return value if isinstance(value, dict) else {"value": value}

    @staticmethod
    def _to_float(value: object) -> float:
        try:
            parsed = float(value)
            return parsed if math.isfinite(parsed) else 0.0
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _fmt(value: float) -> str:
        if value == 0:
            return "0"
        return f"{value:.8f}".rstrip("0").rstrip(".")
