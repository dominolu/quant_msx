from __future__ import annotations

import json
import math
import re
from datetime import datetime
from typing import Any

from sqlalchemy import delete, desc, select

from app.core.config import settings
from app.domain.grid import (
    GridActionResult,
    GridCreateRequest,
    GridDetailView,
    GridEventView,
    GridFillView,
    GridListView,
    GridOrderView,
    GridReconfigureMeta,
    GridReconfigureRequest,
    GridReconfigureResult,
    GridStrategyView,
    GridSummaryView,
)
from app.services.order_service import OrderService
from app.storage.db import SessionLocal
from app.storage.models import (
    GridEventRecord,
    GridFillRecord,
    GridOrderRecord,
    GridReconfigureRecord,
    GridStrategyRecord,
    utc_now,
)

ACTIVE_GRID_STATUSES = {"draft", "starting", "running", "pausing", "paused", "error"}
RUNNING_GRID_STATUSES = {"starting", "running", "pausing", "paused", "error"}
SYMBOL_PATTERN = re.compile(r"^[A-Z0-9_/-]{2,40}$")


class GridService:
    """MSX grid strategy management service.

    This mirrors the gate_arb contract-grid management surface while keeping
    live order execution outside the service until the order layer is ready.
    """

    def __init__(self, order_service: OrderService | None = None) -> None:
        self.order_service = order_service or OrderService()

    async def list_grids(self, status: str | None = None) -> GridListView:
        return self.list_grids_sync(status=status)

    def list_grids_sync(self, status: str | None = None) -> GridListView:
        with SessionLocal() as session:
            stmt = select(GridStrategyRecord).order_by(desc(GridStrategyRecord.id))
            if status:
                stmt = stmt.where(GridStrategyRecord.status == status)
            rows = session.scalars(stmt).all()
            summary = self._build_summary(rows)
        return GridListView(summary=summary, items=[self._to_grid_view(row) for row in rows])

    def get_detail(self, grid_id: int) -> GridDetailView:
        row = self._get_grid_or_raise(grid_id)
        return GridDetailView(
            grid=self._to_grid_view(row),
            orders=self.list_orders(grid_id, limit=120),
            fills=self.list_fills(grid_id, limit=120),
            events=self.list_events(grid_id, limit=50, include_payload=False),
        )

    async def create_grid(self, request: GridCreateRequest) -> GridActionResult:
        self._validate_create_request(request)
        now = utc_now()
        symbol = self._normalize_symbol(request.symbol)
        self._ensure_no_duplicate_grid(symbol)
        leverage = self._to_float(request.leverage, default=1.0)
        margin_usdt = self._to_float(request.margin_usdt)
        grid_levels = int(self._to_float(request.grid_levels))
        range_lower = self._to_float(request.stop_loss_price)
        range_upper = self._to_float(request.take_profit_price)
        base_price = self._initial_price(request.base_price, range_lower, range_upper)

        grid_params = self.compute_grid_orders(
            P_lower=range_lower,
            P_upper=range_upper,
            N=grid_levels,
            M=margin_usdt,
            L=leverage,
            P_current=base_price,
            spacing_mode=request.spacing_mode,
        )
        requested_order_qty = self._to_float(request.order_qty)
        order_qty = requested_order_qty or grid_params["order_qty"]
        initial_position_qty = self._initial_position_qty(
            request.direction,
            order_qty,
            grid_params,
        )

        row = GridStrategyRecord(
            account_id=request.account_id,
            name=request.name.strip(),
            exchange="MSX",
            market=request.market,
            symbol=symbol,
            direction=request.direction,
            margin_mode=request.margin_mode,
            leverage=leverage,
            margin_usdt=margin_usdt,
            spacing_mode=request.spacing_mode,
            grid_spacing_value=grid_params["spacing_value"],
            grid_levels=grid_levels,
            order_qty=order_qty,
            max_position_qty=initial_position_qty,
            max_open_orders_per_side=request.max_open_orders_per_side,
            stop_loss_price=range_lower,
            take_profit_price=range_upper,
            max_loss_usdt=self._to_float(request.max_loss_usdt),
            status="draft",
            base_price=base_price,
            lower_order_price=grid_params["buy_price"],
            upper_order_price=grid_params["sell_price"],
            current_position_qty=0.0,
            invested_usdt=margin_usdt,
            open_price=base_price,
            price_range_lower=range_lower,
            price_range_upper=range_upper,
            health="已创建，等待启动",
            chart_points_json=json.dumps([base_price]),
            created_at=now,
            updated_at=now,
        )
        with SessionLocal() as session:
            session.add(row)
            session.commit()
            session.refresh(row)
            grid_id = row.id
        self._add_event(grid_id, "created", "info", "创建网格")
        if request.start_immediately:
            return await self.start_grid(grid_id)
        return GridActionResult(grid=self._to_grid_view(row), message="created")

    async def start_grid(self, grid_id: int) -> GridActionResult:
        row = self._update_grid_state(
            grid_id,
            status="running",
            health=self._running_health(),
            event_type="started",
            message="启动网格",
            started=True,
            allowed_from={"draft", "paused", "error"},
            check_running_duplicate=True,
        )
        row = await self._submit_opening_orders(row, failure_prefix="启动挂单失败")
        return GridActionResult(grid=self._to_grid_view(row), message="started")

    async def pause_grid(self, grid_id: int) -> GridActionResult:
        row = self._update_grid_state(
            grid_id,
            status="paused",
            health="已暂停",
            event_type="paused",
            message="暂停网格",
            allowed_from={"running"},
        )
        cancelled = await self.order_service.cancel_grid_open_orders(grid_id)
        self._add_event(
            grid_id,
            "orders_cancelled",
            "info",
            f"暂停网格，已撤销挂单 {cancelled} 个",
        )
        row = self._get_grid_or_raise(grid_id)
        return GridActionResult(grid=self._to_grid_view(row), message="paused")

    async def resume_grid(self, grid_id: int) -> GridActionResult:
        row = self._update_grid_state(
            grid_id,
            status="running",
            health=self._running_health(),
            event_type="resumed",
            message="恢复网格",
            allowed_from={"paused"},
            check_running_duplicate=True,
        )
        row = await self._submit_opening_orders(row, failure_prefix="恢复挂单失败")
        return GridActionResult(grid=self._to_grid_view(row), message="resumed")

    async def stop_grid(self, grid_id: int) -> GridActionResult:
        row = self._update_grid_state(
            grid_id,
            status="stopped",
            health="已停止",
            event_type="stopped",
            message="停止网格",
            flatten_position=True,
            allowed_from={"draft", "running", "paused", "error"},
        )
        cancelled = await self.order_service.cancel_grid_open_orders(grid_id)
        self._add_event(
            grid_id,
            "orders_cancelled",
            "info",
            f"停止网格，已撤销挂单 {cancelled} 个",
        )
        row = self._get_grid_or_raise(grid_id)
        return GridActionResult(grid=self._to_grid_view(row), message="stopped")

    def delete_grid(self, grid_id: int) -> GridListView:
        row = self._get_grid_or_raise(grid_id)
        if row.status != "stopped":
            raise ValueError("only stopped grids can be deleted")
        with SessionLocal() as session:
            session.execute(delete(GridEventRecord).where(GridEventRecord.grid_id == grid_id))
            session.execute(delete(GridFillRecord).where(GridFillRecord.grid_id == grid_id))
            session.execute(delete(GridOrderRecord).where(GridOrderRecord.grid_id == grid_id))
            session.execute(
                delete(GridReconfigureRecord).where(GridReconfigureRecord.grid_id == grid_id)
            )
            db_row = session.get(GridStrategyRecord, grid_id)
            if db_row is not None:
                session.delete(db_row)
            session.commit()
        return self.list_grids_sync()

    async def reconfigure_grid(
        self,
        grid_id: int,
        request: GridReconfigureRequest,
    ) -> GridReconfigureResult:
        row = self._get_grid_or_raise(grid_id)
        if row.status not in {"draft", "paused", "stopped"}:
            raise ValueError("only draft, paused, or stopped grids can be reconfigured")

        old_params = {
            "grid_levels": str(row.grid_levels),
            "lower_boundary": self._fmt_price(row.price_range_lower),
            "upper_boundary": self._fmt_price(row.price_range_upper),
            "margin_usdt": self._fmt_money(row.margin_usdt),
        }
        grid_levels = int(self._to_float(request.grid_levels, default=row.grid_levels))
        range_lower = self._to_float(request.lower_boundary, default=row.price_range_lower)
        range_upper = self._to_float(request.upper_boundary, default=row.price_range_upper)
        margin_usdt = self._to_float(request.margin_usdt, default=row.margin_usdt)
        if margin_usdt <= 0:
            raise ValueError("margin_usdt must be greater than 0")
        self._validate_grid_numbers(range_lower, range_upper, grid_levels, row.base_price)
        grid_params = self.compute_grid_orders(
            P_lower=range_lower,
            P_upper=range_upper,
            N=grid_levels,
            M=margin_usdt,
            L=row.leverage,
            P_current=row.base_price,
            spacing_mode=row.spacing_mode,
        )
        target_position_qty = self._initial_position_qty(
            row.direction,
            grid_params["order_qty"],
            grid_params,
        )
        new_params = {
            "grid_levels": str(grid_levels),
            "lower_boundary": self._fmt_price(range_lower),
            "upper_boundary": self._fmt_price(range_upper),
            "margin_usdt": self._fmt_money(margin_usdt),
        }

        with SessionLocal() as session:
            db_row = session.get(GridStrategyRecord, grid_id)
            if db_row is None:
                raise ValueError("grid not found")
            db_row.grid_levels = grid_levels
            db_row.margin_usdt = margin_usdt
            db_row.invested_usdt = margin_usdt
            db_row.price_range_lower = range_lower
            db_row.price_range_upper = range_upper
            db_row.stop_loss_price = range_lower
            db_row.take_profit_price = range_upper
            db_row.grid_spacing_value = grid_params["spacing_value"]
            db_row.order_qty = grid_params["order_qty"]
            db_row.max_position_qty = target_position_qty
            db_row.lower_order_price = grid_params["buy_price"]
            db_row.upper_order_price = grid_params["sell_price"]
            db_row.reconfigure_version += 1
            db_row.updated_at = utc_now()
            version = db_row.reconfigure_version
            session.add(
                GridReconfigureRecord(
                    grid_id=grid_id,
                    version=version,
                    old_params_json=json.dumps(old_params, sort_keys=True),
                    new_params_json=json.dumps(new_params, sort_keys=True),
                    direction=db_row.direction,
                    current_price=db_row.base_price,
                    current_net_position=db_row.current_position_qty,
                    target_net_position=target_position_qty,
                    rebalance_side="",
                    rebalance_qty=0.0,
                    cancelled_order_count=0,
                    submitted_order_count=0,
                    status="completed",
                )
            )
            session.commit()
        self._add_event(
            grid_id,
            "grid_reconfigure_completed",
            "info",
            "网格参数已更新",
            payload={"version": version, "old": old_params, "new": new_params},
        )
        return GridReconfigureResult(
            detail=self.get_detail(grid_id),
            message="reconfigured",
            reconfigure=GridReconfigureMeta(
                version=version,
                old_params=old_params,
                new_params=new_params,
                direction=row.direction,
                current_price=self._fmt_price(row.base_price),
                current_net_position=self._fmt_plain(row.current_position_qty),
                target_net_position=self._fmt_plain(target_position_qty),
                rebalance_side="",
                rebalance_qty="0",
                cancelled_order_count=0,
                submitted_order_count=0,
                status="completed",
            ),
        )

    def ensure_grid_exists(self, grid_id: int) -> None:
        self._get_grid_or_raise(grid_id)

    def list_orders(self, grid_id: int, *, limit: int | None = None) -> list[GridOrderView]:
        with SessionLocal() as session:
            stmt = (
                select(GridOrderRecord)
                .where(GridOrderRecord.grid_id == grid_id)
                .order_by(desc(GridOrderRecord.updated_at))
            )
            if limit is not None:
                stmt = stmt.limit(limit)
            rows = session.scalars(stmt).all()
        return [self._to_order_view(row) for row in rows]

    def list_fills(self, grid_id: int, *, limit: int | None = None) -> list[GridFillView]:
        with SessionLocal() as session:
            stmt = (
                select(GridFillRecord)
                .where(GridFillRecord.grid_id == grid_id)
                .order_by(desc(GridFillRecord.created_at))
            )
            if limit is not None:
                stmt = stmt.limit(limit)
            rows = session.scalars(stmt).all()
        return [self._to_fill_view(row) for row in rows]

    def list_events(
        self,
        grid_id: int,
        *,
        limit: int | None = None,
        include_payload: bool = True,
    ) -> list[GridEventView]:
        with SessionLocal() as session:
            stmt = (
                select(GridEventRecord)
                .where(GridEventRecord.grid_id == grid_id)
                .order_by(desc(GridEventRecord.created_at))
            )
            if limit is not None:
                stmt = stmt.limit(limit)
            rows = session.scalars(stmt).all()
        return [self._to_event_view(row, include_payload=include_payload) for row in rows]

    @staticmethod
    def compute_grid_orders(
        *,
        P_lower: float,
        P_upper: float,
        N: int,
        M: float,
        L: float,
        P_current: float,
        spacing_mode: str,
    ) -> dict[str, float]:
        GridService._validate_grid_numbers(P_lower, P_upper, N, P_current)
        if spacing_mode == "geometric":
            r = (P_upper / P_lower) ** (1.0 / N) - 1.0
            spacing_value = r
            k = int(math.log(P_current / P_lower) / math.log(1.0 + r))
            buy_price = P_current * (1.0 - r)
            sell_price = P_current * (1.0 + r)
        else:
            d = (P_upper - P_lower) / N
            spacing_value = d
            k = int((P_current - P_lower) / d)
            buy_price = P_current - d
            sell_price = P_current + d
        k = max(0, min(k, N - 1))
        value_per_level = M * L / N
        order_qty = value_per_level / P_current
        return {
            "spacing_value": spacing_value,
            "order_qty": order_qty,
            "Q_init": (N - k) * order_qty,
            "buy_price": buy_price,
            "sell_price": sell_price,
            "N_sell": float(N - k),
            "N_buy": float(k),
        }

    def _validate_create_request(self, request: GridCreateRequest) -> None:
        if not request.name.strip():
            raise ValueError("grid name is required")
        if request.exchange != "MSX":
            raise ValueError("only MSX grids are supported")
        self._normalize_symbol(request.symbol)
        if request.market not in {"spot", "futures"}:
            raise ValueError("market must be spot or futures")
        if request.direction not in {"neutral", "long_bias", "short_bias"}:
            raise ValueError("unsupported grid direction")
        if request.margin_mode not in {"cross", "isolated"}:
            raise ValueError("margin_mode must be cross or isolated")
        if request.spacing_mode not in {"geometric", "arithmetic"}:
            raise ValueError("spacing_mode must be geometric or arithmetic")
        grid_levels = int(self._to_float(request.grid_levels))
        range_lower = self._to_float(request.stop_loss_price)
        range_upper = self._to_float(request.take_profit_price)
        base_price = self._initial_price(request.base_price, range_lower, range_upper)
        self._validate_grid_numbers(range_lower, range_upper, grid_levels, base_price)
        if self._to_float(request.margin_usdt) <= 0:
            raise ValueError("margin_usdt must be greater than 0")
        if self._to_float(request.leverage, default=1.0) <= 0:
            raise ValueError("leverage must be greater than 0")
        if self._to_float(request.order_qty) < 0:
            raise ValueError("order_qty must be greater than or equal to 0")
        if request.max_open_orders_per_side <= 0:
            raise ValueError("max_open_orders_per_side must be greater than 0")
        if self._to_float(request.max_loss_usdt) < 0:
            raise ValueError("max_loss_usdt must be greater than or equal to 0")

    def _ensure_no_duplicate_grid(
        self,
        symbol: str,
        *,
        exclude_grid_id: int | None = None,
        statuses: set[str] | None = None,
    ) -> None:
        checked_statuses = statuses or ACTIVE_GRID_STATUSES
        with SessionLocal() as session:
            stmt = select(GridStrategyRecord).where(
                GridStrategyRecord.exchange == "MSX",
                GridStrategyRecord.symbol == symbol,
                GridStrategyRecord.status.in_(tuple(checked_statuses)),
            )
            if exclude_grid_id is not None:
                stmt = stmt.where(GridStrategyRecord.id != exclude_grid_id)
            existing = session.scalar(stmt)
        if existing is not None:
            raise ValueError(f"已经存在 MSX-{symbol} 网格策略，不能重复添加")

    def _get_grid_or_raise(self, grid_id: int) -> GridStrategyRecord:
        with SessionLocal() as session:
            row = session.get(GridStrategyRecord, grid_id)
            if row is None:
                raise ValueError("grid not found")
            session.expunge(row)
            return row

    def _update_grid_state(
        self,
        grid_id: int,
        *,
        status: str,
        health: str,
        event_type: str,
        message: str,
        started: bool = False,
        flatten_position: bool = False,
        allowed_from: set[str] | None = None,
        check_running_duplicate: bool = False,
    ) -> GridStrategyRecord:
        now = utc_now()
        with SessionLocal() as session:
            row = session.get(GridStrategyRecord, grid_id)
            if row is None:
                raise ValueError("grid not found")
            if allowed_from is not None and row.status not in allowed_from:
                allowed = ", ".join(sorted(allowed_from))
                raise ValueError(
                    f"cannot change grid from {row.status} to {status}; allowed: {allowed}"
                )
            if check_running_duplicate:
                duplicate = session.scalar(
                    select(GridStrategyRecord).where(
                        GridStrategyRecord.id != row.id,
                        GridStrategyRecord.exchange == row.exchange,
                        GridStrategyRecord.symbol == row.symbol,
                        GridStrategyRecord.status.in_(tuple(RUNNING_GRID_STATUSES)),
                    )
                )
                if duplicate is not None:
                    raise ValueError(f"已经存在 MSX-{row.symbol} 运行中的网格策略")
            row.status = status
            row.health = health
            row.updated_at = now
            if started and row.started_at is None:
                row.started_at = now
            if flatten_position:
                row.current_position_qty = 0.0
            session.commit()
            session.refresh(row)
            session.expunge(row)
        self._add_event(grid_id, event_type, "info", message)
        return row

    def _add_event(
        self,
        grid_id: int | None,
        event_type: str,
        level: str,
        message: str,
        *,
        payload: dict[str, Any] | None = None,
    ) -> None:
        with SessionLocal() as session:
            session.add(
                GridEventRecord(
                    grid_id=grid_id,
                    event_type=event_type,
                    level=level,
                    message=message,
                    payload_json=json.dumps(payload or {}, sort_keys=True, ensure_ascii=False),
                    created_at=utc_now(),
                )
            )
            session.commit()

    def _mark_grid_error(self, grid_id: int, health: str) -> GridStrategyRecord:
        return self._update_grid_state(
            grid_id,
            status="error",
            health=health,
            event_type="error",
            message=health,
        )

    def _build_initial_order_plan(self, row: GridStrategyRecord) -> list[dict[str, object]]:
        levels = max(1, min(row.max_open_orders_per_side, row.grid_levels))
        orders: list[dict[str, object]] = []
        for offset in range(1, levels + 1):
            buy_price = self._grid_price(row, side="buy", offset=offset)
            sell_price = self._grid_price(row, side="sell", offset=offset)
            if buy_price > row.price_range_lower:
                orders.append(
                    {
                        "side": "buy",
                        "price": self._fmt_price(buy_price),
                        "qty": self._fmt_plain(row.order_qty),
                        "client_order_id": self._client_order_id(row.id, "buy", offset),
                        "role": "grid_buy",
                    }
                )
            if sell_price < row.price_range_upper:
                orders.append(
                    {
                        "side": "sell",
                        "price": self._fmt_price(sell_price),
                        "qty": self._fmt_plain(row.order_qty),
                        "client_order_id": self._client_order_id(row.id, "sell", offset),
                        "role": "grid_sell",
                    }
                )
        if not orders:
            raise ValueError("no grid orders can be placed inside configured price range")
        return orders

    async def _submit_opening_orders(
        self,
        row: GridStrategyRecord,
        *,
        failure_prefix: str,
    ) -> GridStrategyRecord:
        try:
            orders = self._build_initial_order_plan(row)
            submitted = await self.order_service.submit_grid_orders(
                grid_id=row.id,
                account_id=row.account_id,
                market=row.market,
                symbol=row.symbol,
                leverage=self._fmt_plain(row.leverage),
                orders=orders,
            )
            self._add_event(
                row.id,
                "orders_submitted",
                "info",
                f"已提交网格挂单 {len(submitted)} 个",
            )
            return self._get_grid_or_raise(row.id)
        except Exception as exc:
            try:
                cancelled = await self.order_service.cancel_grid_open_orders(row.id)
            except Exception as cancel_exc:
                self._add_event(
                    row.id,
                    "startup_cancel_failed",
                    "error",
                    f"挂单失败后的补偿撤单失败: {cancel_exc}",
                )
            else:
                if cancelled:
                    self._add_event(
                        row.id,
                        "startup_orders_cancelled",
                        "warning",
                        f"挂单失败后已补偿撤单 {cancelled} 个",
                    )
            self._mark_grid_error(row.id, f"{failure_prefix}: {exc}")
            raise

    @staticmethod
    def _grid_price(row: GridStrategyRecord, *, side: str, offset: int) -> float:
        if row.spacing_mode == "geometric":
            multiplier = (1.0 + row.grid_spacing_value) ** offset
            if side == "buy":
                return row.base_price / multiplier
            return row.base_price * multiplier
        distance = row.grid_spacing_value * offset
        return row.base_price - distance if side == "buy" else row.base_price + distance

    @staticmethod
    def _client_order_id(grid_id: int, side: str, offset: int) -> str:
        return f"grid-{grid_id}-{side}-{offset}-{int(utc_now().timestamp())}"

    def _build_summary(self, rows: list[GridStrategyRecord]) -> GridSummaryView:
        running = [row for row in rows if row.status == "running"]
        invested = sum(row.invested_usdt for row in rows)
        return_total = sum(row.total_return_usdt for row in rows)
        grid_profit = sum(row.grid_profit_usdt for row in rows)
        return GridSummaryView(
            running_count=len(running),
            today_fill_count=0,
            today_grid_profit_usdt=self._fmt_signed_money(0),
            total_invested_usdt=self._fmt_money(invested),
            total_return_usdt=self._fmt_signed_money(return_total),
            total_grid_profit_usdt=self._fmt_signed_money(grid_profit),
            live_trading_enabled=settings.live_trading_enabled,
            demo_data_enabled=settings.grid_demo_mode,
            websocket_status="unknown",
            rest_sync_count=sum(row.rest_sync_count for row in rows),
            cache_updated_at=self._iso(utc_now()),
        )

    def _to_grid_view(self, row: GridStrategyRecord) -> GridStrategyView:
        chart_points = self._load_json(row.chart_points_json, [])
        if not isinstance(chart_points, list):
            chart_points = []
        return GridStrategyView(
            id=row.id,
            account_id=row.account_id,
            grid_key=f"{row.exchange}-{row.symbol}",
            name=row.name,
            exchange=row.exchange,
            market=row.market,
            symbol=row.symbol,
            status=row.status,
            direction=row.direction,
            margin_mode=row.margin_mode,
            leverage=self._fmt_plain(row.leverage),
            spacing_mode=row.spacing_mode,
            grid_spacing_value=self._fmt_spacing(row.grid_spacing_value, row.spacing_mode),
            grid_levels=str(row.grid_levels),
            order_qty=self._fmt_plain(row.order_qty),
            order_size_label=f"{self._fmt_plain(row.order_qty)} {row.symbol}",
            runtime_label=self._runtime_label(row),
            invested_usdt=self._fmt_money(row.invested_usdt),
            total_return_usdt=self._fmt_signed_money(row.total_return_usdt),
            total_return_pct=self._fmt_pct(row.total_return_pct),
            grid_profit_usdt=self._fmt_signed_money(row.grid_profit_usdt),
            grid_profit_pct=self._fmt_pct(row.grid_profit_pct),
            unmatched_profit_usdt=self._fmt_signed_money(row.unmatched_profit_usdt),
            unmatched_profit_pct=self._fmt_pct(row.unmatched_profit_pct),
            funding_fee_usdt=self._fmt_signed_money(row.funding_fee_usdt),
            realized_pnl_usdt=self._fmt_signed_money(row.realized_pnl_usdt),
            unrealized_pnl_usdt=self._fmt_signed_money(row.unrealized_pnl_usdt),
            total_pnl_usdt=self._fmt_signed_money(row.total_pnl_usdt),
            grid_annualized_return_pct=self._fmt_pct(row.grid_annualized_return_pct),
            position_annualized_return_pct=self._fmt_pct(row.position_annualized_return_pct),
            current_price=self._fmt_price(row.base_price),
            base_price=self._fmt_price(row.base_price),
            lower_order_price=self._fmt_price(row.lower_order_price),
            upper_order_price=self._fmt_price(row.upper_order_price),
            price_range_lower=self._fmt_price(row.price_range_lower),
            price_range_upper=self._fmt_price(row.price_range_upper),
            price_range=f"{self._fmt_price(row.price_range_lower)} - "
            f"{self._fmt_price(row.price_range_upper)}",
            current_position_qty=self._fmt_plain(row.current_position_qty),
            daily_arbitrage_count=row.daily_arbitrage_count,
            total_arbitrage_count=row.total_arbitrage_count,
            arbitrage_count_label=f"{row.daily_arbitrage_count}/{row.total_arbitrage_count}",
            extra_margin_usdt=self._fmt_money(row.extra_margin_usdt),
            liquidation_price=self._fmt_price(row.liquidation_price),
            open_price=self._fmt_price(row.open_price),
            health=row.health,
            rest_sync_count=row.rest_sync_count,
            reconfigure_version=row.reconfigure_version,
            chart_points=[
                float(point) for point in chart_points if isinstance(point, int | float)
            ],
            started_at=self._iso(row.started_at),
            pnl_updated_at=self._iso(row.pnl_updated_at),
            created_at=self._iso(row.created_at),
            updated_at=self._iso(row.updated_at),
        )

    @staticmethod
    def _to_order_view(row: GridOrderRecord) -> GridOrderView:
        return GridOrderView(
            id=row.id,
            grid_id=row.grid_id,
            round_no=row.round_no,
            exchange_order_id=row.exchange_order_id,
            client_order_id=row.client_order_id,
            side=row.side,
            price=GridService._fmt_price(row.price),
            qty=GridService._fmt_plain(row.qty),
            filled_qty=GridService._fmt_plain(row.filled_qty),
            avg_fill_price=GridService._fmt_price(row.avg_fill_price),
            fee_usdt=GridService._fmt_money(row.fee_usdt),
            status=row.status,
            role=row.role,
            submitted_at=GridService._iso(row.submitted_at),
            updated_at=GridService._iso(row.updated_at),
        )

    @staticmethod
    def _to_fill_view(row: GridFillRecord) -> GridFillView:
        return GridFillView(
            id=row.id,
            grid_id=row.grid_id,
            order_id=row.order_id,
            exchange_trade_id=row.exchange_trade_id,
            side=row.side,
            price=GridService._fmt_price(row.price),
            qty=GridService._fmt_plain(row.qty),
            fee_usdt=GridService._fmt_money(row.fee_usdt),
            base_price_before=GridService._fmt_price(row.base_price_before),
            base_price_after=GridService._fmt_price(row.base_price_after),
            created_at=GridService._iso(row.created_at),
        )

    @staticmethod
    def _to_event_view(row: GridEventRecord, *, include_payload: bool = True) -> GridEventView:
        return GridEventView(
            id=row.id,
            grid_id=row.grid_id,
            event_type=row.event_type,
            level=row.level,
            message=row.message,
            payload=row.payload_json if include_payload else "{}",
            created_at=GridService._iso(row.created_at),
        )

    @staticmethod
    def _initial_price(base_price: str, range_lower: float, range_upper: float) -> float:
        requested = GridService._to_float(base_price)
        if requested > 0:
            return requested
        return (range_lower + range_upper) / 2.0

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        normalized = symbol.strip().upper()
        if not SYMBOL_PATTERN.fullmatch(normalized):
            raise ValueError("symbol must use 2-40 uppercase letters, digits, _, /, or -")
        return normalized

    @staticmethod
    def _initial_position_qty(
        direction: str,
        order_qty: float,
        grid_params: dict[str, float],
    ) -> float:
        if direction == "long_bias":
            return grid_params["Q_init"]
        if direction == "short_bias":
            return order_qty * grid_params["N_buy"]
        return 0.0

    @staticmethod
    def _validate_grid_numbers(
        range_lower: float,
        range_upper: float,
        grid_levels: int,
        base_price: float,
    ) -> None:
        if range_lower <= 0 or range_upper <= range_lower:
            raise ValueError("valid lower and upper boundaries are required")
        if grid_levels <= 0:
            raise ValueError("grid_levels must be greater than 0")
        if base_price <= 0:
            raise ValueError("base_price must be greater than 0")
        if base_price <= range_lower or base_price >= range_upper:
            raise ValueError("base_price must be inside lower and upper boundaries")

    @staticmethod
    def _runtime_label(row: GridStrategyRecord) -> str:
        if row.status == "running":
            return "运行中"
        if row.status == "paused":
            return "已暂停"
        if row.status == "stopped":
            return "已停止"
        if row.status == "draft":
            return "草稿"
        return row.status

    @staticmethod
    def _running_health() -> str:
        if settings.live_trading_enabled:
            return "运行中，订单服务已接入实盘"
        return "模拟运行中，订单服务已接入"

    @staticmethod
    def _load_json(raw: str, default: object) -> object:
        try:
            return json.loads(raw or "")
        except json.JSONDecodeError:
            return default

    @staticmethod
    def _to_float(value: object, default: float = 0.0) -> float:
        try:
            if value is None or value == "":
                return default
            parsed = float(value)
            return parsed if math.isfinite(parsed) else default
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _fmt_plain(value: float) -> str:
        if value == 0:
            return "0"
        return f"{value:.8f}".rstrip("0").rstrip(".")

    @staticmethod
    def _fmt_price(value: float) -> str:
        if value == 0:
            return "0"
        return f"{value:.8f}".rstrip("0").rstrip(".")

    @staticmethod
    def _fmt_money(value: float) -> str:
        return f"{value:.2f}"

    @staticmethod
    def _fmt_signed_money(value: float) -> str:
        return f"{value:+.2f}" if value else "0.00"

    @staticmethod
    def _fmt_pct(value: float) -> str:
        return f"{value:+.2f}%" if value else "0.00%"

    @staticmethod
    def _fmt_spacing(value: float, mode: str) -> str:
        if mode == "geometric":
            formatted = f"{value * 100:.4f}".rstrip("0").rstrip(".")
            return f"{formatted}%"
        return GridService._fmt_price(value)

    @staticmethod
    def _iso(value: object | None) -> str:
        if not isinstance(value, datetime):
            return ""
        return value.isoformat(timespec="seconds") if value is not None else ""


ContractGridService = GridService
