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
    GridFillRequest,
    GridFillView,
    GridListView,
    GridOrderView,
    GridReconfigureMeta,
    GridReconfigureRequest,
    GridReconfigureResult,
    GridStrategyView,
    GridSummaryView,
)
from app.domain.orders import OrderSubmitRequest
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

ACTIVE_GRID_STATUSES = {
    "draft",
    "starting",
    "running",
    "pausing",
    "paused",
    "reconfiguring",
    "error",
}
RUNNING_GRID_STATUSES = {"starting", "running", "pausing", "paused", "reconfiguring", "error"}
SYMBOL_PATTERN = re.compile(r"^[A-Z0-9_/-]{2,40}$")
GRID_REPRICE_ORDER_ROLES = {"lower_buy", "upper_sell"}


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
        try:
            await self._ensure_initial_position(row)
            row = self._get_grid_or_raise(grid_id)
            row = await self._submit_current_pair_orders(row, failure_prefix="启动挂单失败")
        except Exception as exc:
            self._mark_grid_error(grid_id, f"启动失败: {exc}")
            raise
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
        row = await self._submit_current_pair_orders(row, failure_prefix="恢复挂单失败")
        return GridActionResult(grid=self._to_grid_view(row), message="resumed")

    async def stop_grid(self, grid_id: int) -> GridActionResult:
        row = self._get_grid_or_raise(grid_id)
        if row.status not in {"draft", "running", "paused", "error"}:
            raise ValueError("cannot stop grid from current status")
        cancelled = await self.order_service.cancel_grid_open_orders(grid_id)
        self._add_event(
            grid_id,
            "orders_cancelled",
            "info",
            f"停止网格，已撤销挂单 {cancelled} 个",
        )
        await self._flatten_position(row)
        row = self._update_grid_state(
            grid_id,
            status="stopped",
            health="已停止",
            event_type="stopped",
            message="停止网格",
            flatten_position=not settings.live_trading_enabled,
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
        if row.status not in {"draft", "paused", "stopped", "running"}:
            raise ValueError("only draft, running, paused, or stopped grids can be reconfigured")

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
        was_running = row.status == "running"
        cancelled_order_count = 0
        submitted_order_count = 0
        rebalance_side = ""
        rebalance_qty = 0.0

        if was_running:
            cancelled_order_count = await self.order_service.cancel_grid_open_orders(grid_id)
            self._add_event(
                grid_id,
                "grid_reconfigure_orders_cancelled",
                "info",
                f"运行中改参，已撤销旧挂单 {cancelled_order_count} 个",
            )

        with SessionLocal() as session:
            db_row = session.get(GridStrategyRecord, grid_id)
            if db_row is None:
                raise ValueError("grid not found")
            current_position_qty = db_row.current_position_qty
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
            position_delta = target_position_qty - current_position_qty
            if abs(position_delta) > 0:
                rebalance_side = "buy" if position_delta > 0 else "sell"
                rebalance_qty = abs(position_delta)
            session.add(
                GridReconfigureRecord(
                    grid_id=grid_id,
                    version=version,
                    old_params_json=json.dumps(old_params, sort_keys=True),
                    new_params_json=json.dumps(new_params, sort_keys=True),
                    direction=db_row.direction,
                    current_price=db_row.base_price,
                    current_net_position=current_position_qty,
                    target_net_position=target_position_qty,
                    rebalance_side=rebalance_side,
                    rebalance_qty=rebalance_qty,
                    cancelled_order_count=cancelled_order_count,
                    submitted_order_count=submitted_order_count,
                    status="pending" if was_running else "completed",
                )
            )
            session.commit()
        if was_running:
            try:
                if rebalance_qty > 0:
                    await self._rebalance_position(grid_id, rebalance_side, rebalance_qty)
                row = self._get_grid_or_raise(grid_id)
                row = await self._submit_current_pair_orders(
                    row,
                    failure_prefix="改参后挂单失败",
                    cancel_existing=False,
                )
                submitted_order_count = len(self._load_grid_open_orders(grid_id))
                self._mark_reconfigure_completed(
                    grid_id,
                    version,
                    cancelled_order_count=cancelled_order_count,
                    submitted_order_count=submitted_order_count,
                )
            except Exception as exc:
                self._mark_reconfigure_failed(grid_id, version, str(exc))
                self._mark_grid_error(grid_id, f"运行中改参失败: {exc}")
                raise
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
                rebalance_side=rebalance_side,
                rebalance_qty=self._fmt_plain(rebalance_qty),
                cancelled_order_count=cancelled_order_count,
                submitted_order_count=submitted_order_count,
                status="completed",
            ),
        )

    async def handle_order_filled(
        self,
        grid_id: int,
        order_id: int,
        request: GridFillRequest | None = None,
    ) -> GridActionResult:
        row = self._get_grid_or_raise(grid_id)
        if row.status != "running":
            raise ValueError("only running grids can process fills")
        exchange_trade_id = request.exchange_trade_id if request else ""
        if exchange_trade_id and self._fill_exists(exchange_trade_id):
            return GridActionResult(grid=self._to_grid_view(row), message="duplicate_fill_ignored")
        filled = self._get_grid_order_or_raise(grid_id, order_id)
        if filled.status == "filled":
            return GridActionResult(grid=self._to_grid_view(row), message="duplicate_fill_ignored")
        if filled.status not in {"open", "simulated", "partially_filled"}:
            raise ValueError(f"order is not fillable: {filled.status}")
        if filled.role not in GRID_REPRICE_ORDER_ROLES:
            raise ValueError(f"order role cannot reprice grid: {filled.role}")

        fill_price = self._to_float(request.price if request else None, default=filled.price)
        fill_qty = self._to_float(request.qty if request else None, default=filled.qty)
        fee_usdt = self._to_float(request.fee_usdt if request else None)
        if fill_price <= 0 or fill_qty <= 0:
            raise ValueError("valid fill price and qty are required")

        self._mark_counterpart_cancelled(grid_id, filled.id)
        self._reset_grid_after_fill(
            grid_id,
            filled.id,
            fill_price=fill_price,
            fill_qty=fill_qty,
            fee_usdt=fee_usdt,
            exchange_trade_id=exchange_trade_id,
        )
        row = self._get_grid_or_raise(grid_id)
        row = await self._submit_current_pair_orders(
            row,
            failure_prefix="成交后重挂失败",
            cancel_existing=False,
            trigger_order_id=filled.id,
        )
        return GridActionResult(grid=self._to_grid_view(row), message="filled")

    async def sync_grid_from_rest(self, grid_id: int | None = None) -> GridListView:
        rows = self._load_sync_targets(grid_id)
        for row in rows:
            await self._sync_single_grid(row)
        if grid_id is not None:
            return GridListView(summary=self._build_summary(rows), items=[self.get_detail(grid_id).grid])
        return self.list_grids_sync()

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

    def _fill_exists(self, exchange_trade_id: str) -> bool:
        with SessionLocal() as session:
            return (
                session.scalar(
                    select(GridFillRecord.id).where(
                        GridFillRecord.exchange_trade_id == exchange_trade_id
                    )
                )
                is not None
            )

    def _load_sync_targets(self, grid_id: int | None) -> list[GridStrategyRecord]:
        with SessionLocal() as session:
            stmt = select(GridStrategyRecord)
            if grid_id is not None:
                stmt = stmt.where(GridStrategyRecord.id == grid_id)
            else:
                stmt = stmt.where(GridStrategyRecord.status.in_(tuple(ACTIVE_GRID_STATUSES)))
            rows = session.scalars(stmt).all()
            if grid_id is not None and not rows:
                raise ValueError("grid not found")
            for row in rows:
                session.expunge(row)
            return rows

    async def _sync_single_grid(self, row: GridStrategyRecord) -> None:
        position_payload: Any = None
        order_counts: dict[str, int] = {}
        try:
            order_counts = await self._sync_grid_order_statuses(row)
            position_payload = await self.order_service.get_positions(row.account_id, row.symbol)
            position = self._extract_position_snapshot(position_payload, row.symbol)
            self._apply_position_snapshot(row.id, position)
        except Exception as exc:
            self._add_event(row.id, "grid_rest_sync_failed", "warning", f"仓位同步失败: {exc}")
            return
        self._add_event(
            row.id,
            "grid_rest_synced",
            "info",
            "已同步交易所仓位和盈亏",
            payload={"position": position_payload, "orders": order_counts},
        )

    async def _sync_grid_order_statuses(self, row: GridStrategyRecord) -> dict[str, int]:
        open_payload = await self.order_service.get_open_orders(
            row.market,
            row.symbol,
            account_id=row.account_id,
        )
        history_payload = await self.order_service.get_history_orders(
            row.market,
            row.symbol,
            account_id=row.account_id,
        )
        trades_payload = await self.order_service.get_trades(
            row.market,
            row.symbol,
            account_id=row.account_id,
        )
        open_items = self._flatten_payload_items(open_payload)
        history_items = self._flatten_payload_items(history_payload)
        trade_items = self._flatten_payload_items(trades_payload)
        open_ids = {
            key
            for item in open_items
            for key in self._external_order_keys(item)
            if key
        }
        updates = 0
        fill_events: list[tuple[int, GridFillRequest]] = []
        with SessionLocal() as session:
            orders = session.scalars(
                select(GridOrderRecord).where(GridOrderRecord.grid_id == row.id)
            ).all()
            order_by_key: dict[str, int] = {}
            for order in orders:
                for key in (order.exchange_order_id, order.client_order_id):
                    if key:
                        order_by_key[key] = order.id
            for order in orders:
                if order.status in {"filled", "canceled", "failed", "rejected"}:
                    continue
                if order.exchange_order_id in open_ids or order.client_order_id in open_ids:
                    if order.status != "open":
                        order.status = "open"
                        order.updated_at = utc_now()
                        updates += 1
            for item in history_items:
                status = self._normalize_external_order_status(item)
                if not status:
                    continue
                matched_id = self._match_order_by_external_item(order_by_key, item)
                matched = session.get(GridOrderRecord, matched_id) if matched_id else None
                if matched is None or matched.status == status:
                    continue
                if status == "filled" and row.status == "running":
                    fill_events.append((matched.id, self._fill_request_from_external(item, matched)))
                    continue
                matched.status = status
                matched.filled_qty = self._first_float(item, "filled_qty", "filledQty", "dealVol")
                matched.avg_fill_price = self._first_float(
                    item,
                    "avg_fill_price",
                    "avgFillPrice",
                    "dealAvgPrice",
                    "price",
                ) or matched.avg_fill_price
                matched.updated_at = utc_now()
                updates += 1
            session.commit()
        filled_from_history = 0
        for order_id, request in fill_events:
            try:
                result = await self.handle_order_filled(row.id, order_id, request)
            except ValueError:
                continue
            if result.message == "filled":
                filled_from_history += 1
        return {
            "open": len(open_items),
            "history": len(history_items),
            "trades": len(trade_items),
            "updated": updates,
            "filled": filled_from_history,
        }

    @staticmethod
    def _external_order_keys(item: dict[str, Any]) -> list[str]:
        return [
            str(item.get(key) or "")
            for key in (
                "order_id",
                "orderId",
                "id",
                "entrustId",
                "client_order_id",
                "clientOrderId",
                "clientOid",
            )
        ]

    @staticmethod
    def _match_order_by_external_item(
        order_by_key: dict[str, int],
        item: dict[str, Any],
    ) -> int | None:
        for key in GridService._external_order_keys(item):
            if key and key in order_by_key:
                return order_by_key[key]
        return None

    @staticmethod
    def _fill_request_from_external(
        item: dict[str, Any],
        matched: GridOrderRecord,
    ) -> GridFillRequest:
        trade_id = str(
            item.get("trade_id")
            or item.get("tradeId")
            or item.get("dealId")
            or item.get("order_id")
            or item.get("orderId")
            or item.get("id")
            or matched.exchange_order_id
        )
        qty = GridService._first_float(
            item,
            "filled_qty",
            "filledQty",
            "dealVol",
            "qty",
            "vol",
            "size",
        )
        price = GridService._first_float(
            item,
            "avg_fill_price",
            "avgFillPrice",
            "dealAvgPrice",
            "price",
        )
        fee = GridService._first_float(item, "fee", "fee_usdt", "feeUsdt", "commission")
        return GridFillRequest(
            price=GridService._fmt_price(price or matched.price),
            qty=GridService._fmt_plain(qty or matched.qty),
            fee_usdt=GridService._fmt_money(fee),
            exchange_trade_id=f"rest-{trade_id}",
        )

    @staticmethod
    def _normalize_external_order_status(item: dict[str, Any]) -> str:
        raw = str(
            item.get("status")
            or item.get("state")
            or item.get("orderStatus")
            or item.get("entrustStatus")
            or ""
        ).lower()
        if raw in {"filled", "done", "closed", "completed", "2", "3"}:
            return "filled"
        if raw in {"cancelled", "canceled", "cancel", "4", "5"}:
            return "canceled"
        if raw in {"rejected", "failed", "error", "6", "7"}:
            return "failed"
        if raw in {"partial", "partially_filled", "part_filled", "1"}:
            return "partially_filled"
        if raw in {"open", "new", "pending", "0"}:
            return "open"
        return ""

    def _extract_position_snapshot(self, payload: Any, symbol: str) -> dict[str, float]:
        items = self._flatten_payload_items(payload)
        target_symbol = symbol.upper()
        selected: dict[str, Any] = {}
        for item in items:
            raw_symbol = str(
                item.get("symbol")
                or item.get("contract")
                or item.get("instrument")
                or item.get("currency")
                or ""
            ).upper()
            if not raw_symbol or raw_symbol == target_symbol:
                selected = item
                break
        qty = self._first_float(
            selected,
            "qty",
            "position_qty",
            "positionQty",
            "position",
            "volume",
            "vol",
            "size",
            "available",
        )
        side = str(selected.get("side") or selected.get("position_side") or "").lower()
        if side in {"short", "sell"} and qty > 0:
            qty = -qty
        return {
            "qty": qty,
            "realized_pnl": self._first_float(
                selected,
                "realized_pnl",
                "realizedPnl",
                "closed_pnl",
                "closedPnl",
                "rpnl",
            ),
            "unrealized_pnl": self._first_float(
                selected,
                "unrealized_pnl",
                "unrealizedPnl",
                "upnl",
                "profit",
            ),
            "funding_fee": self._first_float(
                selected,
                "funding_fee",
                "fundingFee",
                "funding",
            ),
            "mark_price": self._first_float(selected, "mark_price", "markPrice", "last", "price"),
        }

    def _apply_position_snapshot(self, grid_id: int, snapshot: dict[str, float]) -> None:
        now = utc_now()
        with SessionLocal() as session:
            row = session.get(GridStrategyRecord, grid_id)
            if row is None:
                raise ValueError("grid not found")
            row.current_position_qty = snapshot["qty"]
            row.realized_pnl_usdt = snapshot["realized_pnl"]
            row.unrealized_pnl_usdt = snapshot["unrealized_pnl"]
            row.funding_fee_usdt = snapshot["funding_fee"]
            row.total_pnl_usdt = row.realized_pnl_usdt + row.unrealized_pnl_usdt
            row.total_return_usdt = row.total_pnl_usdt + row.grid_profit_usdt
            row.total_return_pct = (
                row.total_return_usdt / row.invested_usdt * 100 if row.invested_usdt > 0 else 0.0
            )
            row.unmatched_profit_usdt = row.total_return_usdt - row.grid_profit_usdt
            row.unmatched_profit_pct = (
                row.unmatched_profit_usdt / row.invested_usdt * 100
                if row.invested_usdt > 0
                else 0.0
            )
            if snapshot["mark_price"] > 0:
                row.base_price = snapshot["mark_price"]
            row.rest_sync_count += 1
            row.pnl_updated_at = now
            row.updated_at = now
            session.commit()

    @staticmethod
    def _flatten_payload_items(payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if not isinstance(payload, dict):
            return []
        for key in ("data", "items", "list", "positions", "result"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
            if isinstance(value, dict):
                nested = GridService._flatten_payload_items(value)
                if nested:
                    return nested
        return [payload]

    @staticmethod
    def _first_float(payload: dict[str, Any], *keys: str) -> float:
        for key in keys:
            value = payload.get(key)
            parsed = GridService._to_float(value)
            if parsed:
                return parsed
        return 0.0

    async def _ensure_initial_position(self, row: GridStrategyRecord) -> None:
        target_qty = self._to_float(row.max_position_qty)
        if row.direction == "short_bias":
            target_qty = -target_qty
        if row.direction == "neutral" or abs(target_qty) <= 0:
            return
        delta = target_qty - self._to_float(row.current_position_qty)
        if abs(delta) <= 0:
            return
        side = "buy" if delta > 0 else "sell"
        await self._rebalance_position(row.id, side, abs(delta), event_type="initial_position")

    async def _flatten_position(self, row: GridStrategyRecord) -> None:
        current_qty = self._to_float(row.current_position_qty)
        if abs(current_qty) <= 0:
            return
        side = "sell" if current_qty > 0 else "buy"
        await self._rebalance_position(row.id, side, abs(current_qty), reduce_only=True)

    async def _rebalance_position(
        self,
        grid_id: int,
        side: str,
        qty: float,
        *,
        reduce_only: bool = False,
        event_type: str = "grid_rebalanced",
    ) -> None:
        row = self._get_grid_or_raise(grid_id)
        if qty <= 0:
            return
        order = await self.order_service.place_order(
            OrderSubmitRequest(
                account_id=row.account_id,
                source="grid",
                source_id=grid_id,
                market=row.market,  # type: ignore[arg-type]
                symbol=row.symbol,
                side=side,  # type: ignore[arg-type]
                order_type="market",
                qty=self._fmt_plain(qty),
                leverage=self._fmt_plain(row.leverage),
                reduce_only=reduce_only,
                client_order_id=self._client_order_id(row.id, row.current_round, event_type),
            )
        )
        if not order.live:
            signed_delta = qty if side == "buy" else -qty
            with SessionLocal() as session:
                db_row = session.get(GridStrategyRecord, grid_id)
                if db_row is not None:
                    db_row.current_position_qty += signed_delta
                    db_row.updated_at = utc_now()
                session.commit()
        self._add_event(
            grid_id,
            event_type,
            "info",
            f"仓位调整 {side} {self._fmt_plain(qty)}",
            payload={
                "side": side,
                "qty": qty,
                "reduce_only": reduce_only,
                "live": order.live,
                "optimistic_position_update": not order.live,
            },
        )

    def _mark_reconfigure_completed(
        self,
        grid_id: int,
        version: int,
        *,
        cancelled_order_count: int,
        submitted_order_count: int,
    ) -> None:
        with SessionLocal() as session:
            row = session.scalar(
                select(GridReconfigureRecord).where(
                    GridReconfigureRecord.grid_id == grid_id,
                    GridReconfigureRecord.version == version,
                )
            )
            if row is not None:
                row.cancelled_order_count = cancelled_order_count
                row.submitted_order_count = submitted_order_count
                row.status = "completed"
            session.commit()

    def _mark_reconfigure_failed(self, grid_id: int, version: int, error_message: str) -> None:
        with SessionLocal() as session:
            row = session.scalar(
                select(GridReconfigureRecord).where(
                    GridReconfigureRecord.grid_id == grid_id,
                    GridReconfigureRecord.version == version,
                )
            )
            if row is not None:
                row.status = "failed"
                row.error_message = error_message
            session.commit()

    def _mark_grid_error(self, grid_id: int, health: str) -> GridStrategyRecord:
        return self._update_grid_state(
            grid_id,
            status="error",
            health=health,
            event_type="error",
            message=health,
        )

    def _build_current_pair_order_plan(
        self,
        row: GridStrategyRecord,
        *,
        trigger_order_id: int | None = None,
    ) -> list[dict[str, object]]:
        grid_params = self.compute_grid_orders(
            P_lower=row.price_range_lower,
            P_upper=row.price_range_upper,
            N=row.grid_levels,
            M=row.margin_usdt,
            L=row.leverage,
            P_current=row.base_price,
            spacing_mode=row.spacing_mode,
        )
        lower_price = max(float(grid_params["buy_price"]), row.price_range_lower)
        upper_price = min(float(grid_params["sell_price"]), row.price_range_upper)
        self._set_grid_order_prices(row.id, lower_price, upper_price)

        orders: list[dict[str, object]] = []
        if lower_price >= row.price_range_lower and lower_price < row.base_price:
            orders.append(
                {
                    "side": "buy",
                    "price": self._fmt_price(lower_price),
                    "qty": self._fmt_plain(row.order_qty),
                    "client_order_id": self._client_order_id(
                        row.id,
                        row.current_round,
                        "lower_buy",
                    ),
                    "role": "lower_buy",
                    "round_no": row.current_round,
                    "paired_open_order_id": trigger_order_id,
                }
            )
        if upper_price <= row.price_range_upper and upper_price > row.base_price:
            orders.append(
                {
                    "side": "sell",
                    "price": self._fmt_price(upper_price),
                    "qty": self._fmt_plain(row.order_qty),
                    "client_order_id": self._client_order_id(
                        row.id,
                        row.current_round,
                        "upper_sell",
                    ),
                    "role": "upper_sell",
                    "round_no": row.current_round,
                    "paired_open_order_id": trigger_order_id,
                }
            )
        if not orders:
            raise ValueError("no grid orders can be placed inside configured price range")
        return orders

    async def _submit_current_pair_orders(
        self,
        row: GridStrategyRecord,
        *,
        failure_prefix: str,
        cancel_existing: bool = True,
        trigger_order_id: int | None = None,
    ) -> GridStrategyRecord:
        try:
            if cancel_existing:
                await self.order_service.cancel_grid_open_orders(row.id)
            row = self._get_grid_or_raise(row.id)
            orders = self._build_current_pair_order_plan(
                row,
                trigger_order_id=trigger_order_id,
            )
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
                f"已提交当前轮挂单 {len(submitted)} 个",
                payload={
                    "round": row.current_round,
                    "roles": [str(item.get("role")) for item in orders],
                },
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
    def _client_order_id(grid_id: int, round_no: int, role: str) -> str:
        return f"grid-{grid_id}-{round_no}-{role}-{int(utc_now().timestamp())}"

    def _set_grid_order_prices(self, grid_id: int, lower_price: float, upper_price: float) -> None:
        with SessionLocal() as session:
            row = session.get(GridStrategyRecord, grid_id)
            if row is None:
                return
            row.lower_order_price = lower_price
            row.upper_order_price = upper_price
            row.updated_at = utc_now()
            session.commit()

    def _get_grid_order_or_raise(self, grid_id: int, order_id: int) -> GridOrderRecord:
        with SessionLocal() as session:
            row = session.get(GridOrderRecord, order_id)
            if row is None or row.grid_id != grid_id:
                raise ValueError("grid order not found")
            session.expunge(row)
            return row

    def _load_grid_open_orders(self, grid_id: int) -> list[GridOrderRecord]:
        with SessionLocal() as session:
            rows = session.scalars(
                select(GridOrderRecord).where(
                    GridOrderRecord.grid_id == grid_id,
                    GridOrderRecord.status.in_(("open", "simulated", "partially_filled")),
                )
            ).all()
            for row in rows:
                session.expunge(row)
            return rows

    def _mark_counterpart_cancelled(self, grid_id: int, filled_order_id: int) -> None:
        with SessionLocal() as session:
            rows = session.scalars(
                select(GridOrderRecord).where(
                    GridOrderRecord.grid_id == grid_id,
                    GridOrderRecord.id != filled_order_id,
                    GridOrderRecord.status.in_(("open", "simulated", "partially_filled")),
                )
            ).all()
            for row in rows:
                row.status = "canceled"
                row.updated_at = utc_now()
            session.commit()
        if rows:
            self._add_event(grid_id, "counterpart_cancelled", "info", "成交后已撤销对侧订单")

    def _reset_grid_after_fill(
        self,
        grid_id: int,
        filled_order_id: int,
        *,
        fill_price: float,
        fill_qty: float,
        fee_usdt: float,
        exchange_trade_id: str,
    ) -> None:
        now = utc_now()
        with SessionLocal() as session:
            grid = session.get(GridStrategyRecord, grid_id)
            filled = session.get(GridOrderRecord, filled_order_id)
            if grid is None or filled is None:
                raise ValueError("grid or filled order not found")
            base_price_before = grid.base_price
            filled.status = "filled"
            filled.filled_qty = fill_qty
            filled.avg_fill_price = fill_price
            filled.fee_usdt = fee_usdt
            filled.updated_at = now
            if filled.side == "buy":
                grid.current_position_qty += fill_qty
            elif filled.side == "sell":
                grid.current_position_qty -= fill_qty

            grid.last_fill_price = fill_price
            grid.base_price = fill_price
            grid.current_round += 1
            if self._is_realized_grid_fill(grid.direction, filled.role):
                grid.daily_arbitrage_count += 1
                grid.total_arbitrage_count += 1
            grid_params = self.compute_grid_orders(
                P_lower=grid.price_range_lower,
                P_upper=grid.price_range_upper,
                N=grid.grid_levels,
                M=grid.margin_usdt,
                L=grid.leverage,
                P_current=fill_price,
                spacing_mode=grid.spacing_mode,
            )
            grid.lower_order_price = max(float(grid_params["buy_price"]), grid.price_range_lower)
            grid.upper_order_price = min(float(grid_params["sell_price"]), grid.price_range_upper)
            fill = GridFillRecord(
                grid_id=grid_id,
                order_id=filled_order_id,
                exchange_trade_id=exchange_trade_id
                or f"grid-fill-{grid_id}-{filled_order_id}-{int(now.timestamp())}",
                side=filled.side,
                price=fill_price,
                qty=fill_qty,
                fee_usdt=fee_usdt,
                grid_profit_usdt=0.0,
                rpnl_usdt=0.0,
                base_price_before=base_price_before,
                base_price_after=fill_price,
                created_at=now,
            )
            fill.grid_profit_usdt = self._grid_profit_for_fill(session, fill, filled, grid)
            fill.rpnl_usdt = fill.grid_profit_usdt
            session.add(fill)
            if fill.grid_profit_usdt > 0:
                grid.grid_profit_usdt += fill.grid_profit_usdt
                grid.grid_profit_pct = (
                    grid.grid_profit_usdt / grid.invested_usdt * 100
                    if grid.invested_usdt > 0
                    else 0.0
                )
            order_pnl = self._grid_order_flow_pnl(session, grid, mark_price=fill_price)
            total_return = order_pnl["total_pnl"]
            realized_pnl = order_pnl["realized_pnl"]
            unrealized_pnl = order_pnl["unrealized_pnl"]
            unmatched_profit = total_return - grid.grid_profit_usdt
            grid.unmatched_profit_usdt = unmatched_profit
            grid.unmatched_profit_pct = (
                unmatched_profit / grid.invested_usdt * 100
                if grid.invested_usdt > 0
                else 0.0
            )
            grid.realized_pnl_usdt = realized_pnl
            grid.unrealized_pnl_usdt = unrealized_pnl
            grid.total_pnl_usdt = total_return
            grid.total_return_usdt = total_return
            grid.total_return_pct = (
                grid.total_return_usdt / grid.invested_usdt * 100
                if grid.invested_usdt > 0
                else 0.0
            )
            grid.grid_annualized_return_pct = self._annualized_pct(
                grid.grid_profit_pct,
                grid.started_at or grid.created_at,
                now,
            )
            grid.position_annualized_return_pct = self._annualized_pct(
                grid.total_return_pct,
                grid.started_at or grid.created_at,
                now,
            )
            grid.pnl_updated_at = now
            grid.updated_at = now
            session.commit()
        self._add_event(grid_id, "grid_repriced", "info", "成交后已按最新成交价重置网格")

    @staticmethod
    def _is_realized_grid_fill(direction: str, role: str) -> bool:
        if direction == "long_bias":
            return role == "upper_sell"
        if direction == "short_bias":
            return role == "lower_buy"
        if direction == "neutral":
            return role in GRID_REPRICE_ORDER_ROLES
        return False

    def _grid_profit_for_fill(
        self,
        session: Any,
        fill: GridFillRecord,
        order: GridOrderRecord,
        grid: GridStrategyRecord,
    ) -> float:
        if not self._is_realized_grid_fill(grid.direction, order.role):
            return 0.0
        paired = self._paired_open_order_for_close(session, grid.direction, order)
        if paired is None:
            pnl = self._grid_profit_from_base_price(grid.direction, fill, order, fill.qty)
            return max(self._to_float(pnl), 0.0)
        open_qty, open_avg_price, open_fee_total = self._order_fill_totals(session, paired)
        if open_qty <= 0 or open_avg_price <= 0:
            return 0.0
        remaining = max(open_qty - self._matched_close_qty_for_open_order(session, paired.id), 0.0)
        matched_qty = min(fill.qty, remaining)
        if matched_qty <= 0 or fill.qty <= 0:
            return 0.0
        close_fee = fill.fee_usdt * matched_qty / fill.qty
        open_fee = open_fee_total * matched_qty / open_qty
        if (
            grid.direction == "short_bias"
            or (grid.direction == "neutral" and paired.side == "sell")
        ):
            pnl = (open_avg_price - fill.price) * matched_qty - open_fee - close_fee
        else:
            pnl = (fill.price - open_avg_price) * matched_qty - open_fee - close_fee
        return max(pnl, 0.0)

    def _grid_profit_from_base_price(
        self,
        direction: str,
        fill: GridFillRecord,
        order: GridOrderRecord,
        matched_qty: float,
    ) -> float | None:
        if matched_qty <= 0:
            return None
        base_price = self._to_float(fill.base_price_before)
        price = self._to_float(fill.price)
        if base_price <= 0 or price <= 0:
            return None
        fee = self._to_float(fill.fee_usdt)
        if direction == "long_bias" and order.role == "upper_sell":
            return (price - base_price) * matched_qty - fee
        if direction == "short_bias" and order.role == "lower_buy":
            return (base_price - price) * matched_qty - fee
        if direction == "neutral":
            if (fill.side or order.side or "").lower() == "sell":
                return (price - base_price) * matched_qty - fee
            return (base_price - price) * matched_qty - fee
        return None

    def _paired_open_order_for_close(
        self,
        session: Any,
        direction: str,
        close_order: GridOrderRecord,
    ) -> GridOrderRecord | None:
        if close_order.paired_open_order_id:
            paired = session.get(GridOrderRecord, close_order.paired_open_order_id)
            if paired is not None:
                return paired
        if direction == "long_bias":
            roles = ("lower_buy",)
            if close_order.role != "upper_sell":
                return None
        elif direction == "short_bias":
            roles = ("upper_sell",)
            if close_order.role != "lower_buy":
                return None
        else:
            roles = ("lower_buy",) if close_order.side == "sell" else ("upper_sell",)
        return session.scalar(
            select(GridOrderRecord)
            .where(
                GridOrderRecord.grid_id == close_order.grid_id,
                GridOrderRecord.id != close_order.id,
                GridOrderRecord.role.in_(roles),
                GridOrderRecord.filled_qty > 0,
            )
            .order_by(desc(GridOrderRecord.updated_at), desc(GridOrderRecord.id))
        )

    def _order_fill_totals(
        self,
        session: Any,
        order: GridOrderRecord,
    ) -> tuple[float, float, float]:
        fills = session.scalars(
            select(GridFillRecord).where(GridFillRecord.order_id == order.id)
        ).all()
        if fills:
            qty = sum(self._to_float(fill.qty) for fill in fills)
            notional = sum(self._to_float(fill.qty) * self._to_float(fill.price) for fill in fills)
            fee = sum(self._to_float(fill.fee_usdt) for fill in fills)
            avg_price = notional / qty if qty > 0 else 0.0
            return qty, avg_price, fee
        qty = self._to_float(order.filled_qty)
        price = self._to_float(order.avg_fill_price) or self._to_float(order.price)
        return qty, price, self._to_float(order.fee_usdt)

    def _matched_close_qty_for_open_order(self, session: Any, open_order_id: int) -> float:
        close_orders = session.scalars(
            select(GridOrderRecord).where(GridOrderRecord.paired_open_order_id == open_order_id)
        ).all()
        return sum(self._to_float(order.filled_qty) for order in close_orders)

    def _grid_order_flow_pnl(
        self,
        session: Any,
        row: GridStrategyRecord,
        *,
        mark_price: float,
    ) -> dict[str, float]:
        orders = session.scalars(
            select(GridOrderRecord)
            .where(GridOrderRecord.grid_id == row.id, GridOrderRecord.filled_qty > 0)
            .order_by(GridOrderRecord.submitted_at, GridOrderRecord.id)
        ).all()
        buy_qty = buy_notional = sell_qty = sell_notional = fee_total = 0.0
        position_qty = 0.0
        position_cost = 0.0
        for order in orders:
            qty = self._to_float(order.filled_qty)
            price = self._to_float(order.avg_fill_price) or self._to_float(order.price)
            if qty <= 0 or price <= 0:
                continue
            notional = qty * price
            fee_total += self._to_float(order.fee_usdt)
            if order.side == "buy":
                buy_qty += qty
                buy_notional += notional
                if position_qty < 0:
                    matched_qty = min(qty, -position_qty)
                    short_avg_price = position_cost / position_qty if position_qty else 0.0
                    position_qty += matched_qty
                    position_cost += matched_qty * short_avg_price
                    extra_qty = qty - matched_qty
                    if extra_qty > 0:
                        position_qty += extra_qty
                        position_cost += extra_qty * price
                else:
                    position_qty += qty
                    position_cost += notional
                continue
            if order.side == "sell":
                sell_qty += qty
                sell_notional += notional
                if position_qty > 0:
                    matched_qty = min(qty, position_qty)
                    long_avg_cost = position_cost / position_qty
                    position_qty -= matched_qty
                    position_cost -= matched_qty * long_avg_cost
                    extra_qty = qty - matched_qty
                    if extra_qty > 0:
                        position_qty -= extra_qty
                        position_cost -= extra_qty * price
                else:
                    position_qty -= qty
                    position_cost -= notional
        order_net_qty = buy_qty - sell_qty
        mark_value = order_net_qty * mark_price
        total_pnl = sell_notional + mark_value - buy_notional - fee_total
        unrealized_pnl = mark_value - position_cost
        realized_pnl = total_pnl - unrealized_pnl
        return {
            "order_net_qty": order_net_qty,
            "realized_pnl": realized_pnl,
            "unrealized_pnl": unrealized_pnl,
            "total_pnl": total_pnl,
        }

    @staticmethod
    def _annualized_pct(return_pct: float, started_at: datetime | None, now: datetime) -> float:
        if started_at is None:
            return 0.0
        elapsed_seconds = (now - started_at).total_seconds()
        if elapsed_seconds <= 0:
            return 0.0
        return return_pct * (365 * 24 * 60 * 60) / elapsed_seconds

    def _build_summary(self, rows: list[GridStrategyRecord]) -> GridSummaryView:
        running = [row for row in rows if row.status == "running"]
        invested = sum(row.invested_usdt for row in rows)
        return_total = sum(row.total_return_usdt for row in rows)
        grid_profit = sum(row.grid_profit_usdt for row in rows)
        today_start = utc_now().replace(hour=0, minute=0, second=0, microsecond=0)
        grid_ids = [row.id for row in rows]
        today_fill_count = 0
        today_grid_profit = 0.0
        if grid_ids:
            with SessionLocal() as session:
                fills = session.scalars(
                    select(GridFillRecord).where(
                        GridFillRecord.grid_id.in_(grid_ids),
                        GridFillRecord.created_at >= today_start,
                    )
                ).all()
                today_fill_count = len(fills)
                today_grid_profit = sum(fill.grid_profit_usdt for fill in fills)
        return GridSummaryView(
            running_count=len(running),
            today_fill_count=today_fill_count,
            today_grid_profit_usdt=self._fmt_signed_money(today_grid_profit),
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
            current_round=row.current_round,
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
            grid_profit_usdt=GridService._fmt_money(row.grid_profit_usdt),
            rpnl_usdt=GridService._fmt_money(row.rpnl_usdt),
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
