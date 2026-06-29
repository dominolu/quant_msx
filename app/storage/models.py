from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.storage.db import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class ExchangeAccountRecord(Base):
    __tablename__ = "exchange_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    account_type: Mapped[str] = mapped_column(String(16), default="cex", nullable=False)
    exchange: Mapped[str] = mapped_column(String(64), default="MSX", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="unverified", nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    credentials_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    credential_fingerprint: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    credential_summary_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    permissions_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    connection_config_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    latest_balance_usdt: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    latest_equity_usdt: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    equity_curve_points_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str] = mapped_column(Text, default="", nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)


class AccountBalanceSnapshotRecord(Base):
    __tablename__ = "account_balance_snapshots"
    __table_args__ = (
        Index("idx_account_balance_snapshots_account_created", "account_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("exchange_accounts.id"), nullable=False)
    balance_usdt: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    equity_usdt: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    error_message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    raw_payload_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)


class SchedulerLockRecord(Base):
    __tablename__ = "scheduler_locks"

    name: Mapped[str] = mapped_column(String(128), primary_key=True)
    owner: Mapped[str] = mapped_column(String(128), default="", nullable=False)
    locked_until: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)


class GridStrategyRecord(Base):
    __tablename__ = "grid_strategies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int | None] = mapped_column(
        ForeignKey("exchange_accounts.id"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    exchange: Mapped[str] = mapped_column(String(32), default="MSX", nullable=False)
    market: Mapped[str] = mapped_column(String(16), default="futures", nullable=False)
    symbol: Mapped[str] = mapped_column(String(64), nullable=False)
    direction: Mapped[str] = mapped_column(String(32), default="neutral", nullable=False)
    margin_mode: Mapped[str] = mapped_column(String(32), default="cross", nullable=False)
    leverage: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    margin_usdt: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    spacing_mode: Mapped[str] = mapped_column(String(32), default="geometric", nullable=False)
    grid_spacing_value: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    grid_levels: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    order_qty: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    max_position_qty: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    max_open_orders_per_side: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    stop_loss_price: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    take_profit_price: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    max_loss_usdt: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    base_price: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    lower_order_price: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    upper_order_price: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    last_fill_price: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    current_round: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    current_position_qty: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    invested_usdt: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    total_return_usdt: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    total_return_pct: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    grid_profit_usdt: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    grid_profit_pct: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    unmatched_profit_usdt: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    unmatched_profit_pct: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    funding_fee_usdt: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    realized_pnl_usdt: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    unrealized_pnl_usdt: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    total_pnl_usdt: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    grid_annualized_return_pct: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    position_annualized_return_pct: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    price_range_lower: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    price_range_upper: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    daily_arbitrage_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_arbitrage_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    extra_margin_usdt: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    liquidation_price: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    open_price: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    health: Mapped[str] = mapped_column(String(128), default="", nullable=False)
    rest_sync_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reconfigure_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    chart_points_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    pnl_updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)


class GridOrderRecord(Base):
    __tablename__ = "grid_orders"
    __table_args__ = (Index("idx_grid_orders_grid_updated", "grid_id", "updated_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    grid_id: Mapped[int] = mapped_column(ForeignKey("grid_strategies.id"), nullable=False)
    round_no: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    exchange_order_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    client_order_id: Mapped[str] = mapped_column(String(128), default="", nullable=False)
    side: Mapped[str] = mapped_column(String(16), nullable=False)
    price: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    qty: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    filled_qty: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    avg_fill_price: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    fee_usdt: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="open", nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    paired_open_order_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)


class GridFillRecord(Base):
    __tablename__ = "grid_fills"
    __table_args__ = (Index("idx_grid_fills_grid_created", "grid_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    grid_id: Mapped[int] = mapped_column(ForeignKey("grid_strategies.id"), nullable=False)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("grid_orders.id"), nullable=True)
    exchange_trade_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    side: Mapped[str] = mapped_column(String(16), nullable=False)
    price: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    qty: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    fee_usdt: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    grid_profit_usdt: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    rpnl_usdt: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    base_price_before: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    base_price_after: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)


class GridEventRecord(Base):
    __tablename__ = "grid_events"
    __table_args__ = (
        Index("idx_grid_events_grid_created", "grid_id", "created_at"),
        Index("idx_grid_events_type_grid", "event_type", "grid_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    grid_id: Mapped[int | None] = mapped_column(ForeignKey("grid_strategies.id"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    level: Mapped[str] = mapped_column(String(16), default="info", nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)


class GridReconfigureRecord(Base):
    __tablename__ = "grid_reconfigure_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    grid_id: Mapped[int] = mapped_column(ForeignKey("grid_strategies.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    old_params_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    new_params_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    direction: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    current_price: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    current_net_position: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    target_net_position: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    rebalance_side: Mapped[str] = mapped_column(String(16), default="", nullable=False)
    rebalance_qty: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    cancelled_order_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    submitted_order_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    error_message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)


class TradingOrderRecord(Base):
    __tablename__ = "trading_orders"
    __table_args__ = (
        Index("idx_trading_orders_source", "source", "source_id"),
        Index("idx_trading_orders_symbol_status", "symbol", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[int | None] = mapped_column(
        ForeignKey("exchange_accounts.id"),
        nullable=True,
    )
    source: Mapped[str] = mapped_column(String(32), default="manual", nullable=False)
    source_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    market: Mapped[str] = mapped_column(String(16), default="futures", nullable=False)
    symbol: Mapped[str] = mapped_column(String(64), nullable=False)
    side: Mapped[str] = mapped_column(String(16), nullable=False)
    order_type: Mapped[str] = mapped_column(String(16), default="limit", nullable=False)
    price: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    qty: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    filled_qty: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    avg_fill_price: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    client_order_id: Mapped[str] = mapped_column(String(128), default="", nullable=False)
    exchange_order_id: Mapped[str] = mapped_column(String(128), default="", nullable=False)
    live: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    request_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    response_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    error_message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)


ContractGridStrategyRecord = GridStrategyRecord
ContractGridOrderRecord = GridOrderRecord
ContractGridFillRecord = GridFillRecord
ContractGridEventRecord = GridEventRecord
ContractGridReconfigureRecord = GridReconfigureRecord
