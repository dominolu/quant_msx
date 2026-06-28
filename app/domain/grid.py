from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class GridCreateRequest(BaseModel):
    account_id: int | None = None
    name: str
    exchange: str = "MSX"
    market: str = "futures"
    symbol: str
    direction: str = "neutral"
    margin_mode: str = "cross"
    leverage: str = "1"
    margin_usdt: str = "0"
    spacing_mode: str = "geometric"
    grid_spacing_value: str = "0"
    grid_levels: str = "0"
    order_qty: str = "0"
    max_open_orders_per_side: int = 1
    stop_loss_price: str = "0"
    take_profit_price: str = "0"
    max_loss_usdt: str = "0"
    base_price: str = "0"
    start_immediately: bool = False

    @field_validator("exchange")
    @classmethod
    def normalize_exchange(cls, value: str) -> str:
        normalized = value.strip().upper()
        if normalized != "MSX":
            raise ValueError("only MSX grids are supported")
        return normalized


class GridSummaryView(BaseModel):
    running_count: int = 0
    today_fill_count: int = 0
    today_grid_profit_usdt: str = "0"
    total_invested_usdt: str = "0"
    total_return_usdt: str = "0"
    total_grid_profit_usdt: str = "0"
    live_trading_enabled: bool = False
    demo_data_enabled: bool = False
    websocket_status: str = "unknown"
    rest_sync_count: int = 0
    cache_updated_at: str = ""


class GridStrategyView(BaseModel):
    id: int
    account_id: int | None = None
    grid_key: str
    name: str
    exchange: str
    market: str
    symbol: str
    status: str
    direction: str
    margin_mode: str
    leverage: str
    spacing_mode: str
    grid_spacing_value: str
    grid_levels: str
    order_qty: str
    order_size_label: str
    runtime_label: str
    invested_usdt: str
    total_return_usdt: str
    total_return_pct: str
    grid_profit_usdt: str
    grid_profit_pct: str
    unmatched_profit_usdt: str
    unmatched_profit_pct: str
    funding_fee_usdt: str
    realized_pnl_usdt: str
    unrealized_pnl_usdt: str
    total_pnl_usdt: str
    grid_annualized_return_pct: str
    position_annualized_return_pct: str
    current_price: str
    base_price: str
    lower_order_price: str
    upper_order_price: str
    price_range_lower: str
    price_range_upper: str
    price_range: str
    current_position_qty: str
    daily_arbitrage_count: int
    total_arbitrage_count: int
    arbitrage_count_label: str
    extra_margin_usdt: str
    liquidation_price: str
    open_price: str
    health: str
    rest_sync_count: int
    reconfigure_version: int = 0
    chart_points: list[float] = Field(default_factory=list)
    started_at: str = ""
    pnl_updated_at: str = ""
    created_at: str
    updated_at: str


class GridListView(BaseModel):
    summary: GridSummaryView
    items: list[GridStrategyView] = Field(default_factory=list)


class GridOrderView(BaseModel):
    id: int
    grid_id: int
    round_no: int
    exchange_order_id: str
    client_order_id: str
    side: str
    price: str
    qty: str
    filled_qty: str
    avg_fill_price: str
    fee_usdt: str
    status: str
    role: str
    submitted_at: str = ""
    updated_at: str


class GridFillView(BaseModel):
    id: int
    grid_id: int
    order_id: int | None = None
    exchange_trade_id: str
    side: str
    price: str
    qty: str
    fee_usdt: str
    base_price_before: str
    base_price_after: str
    created_at: str


class GridEventView(BaseModel):
    id: int
    grid_id: int | None = None
    event_type: str
    level: str
    message: str
    payload: str = "{}"
    created_at: str


class GridDetailView(BaseModel):
    grid: GridStrategyView
    orders: list[GridOrderView] = Field(default_factory=list)
    fills: list[GridFillView] = Field(default_factory=list)
    events: list[GridEventView] = Field(default_factory=list)


class GridActionResult(BaseModel):
    grid: GridStrategyView
    message: str


class GridReconfigureRequest(BaseModel):
    grid_levels: str | None = None
    lower_boundary: str | None = None
    upper_boundary: str | None = None
    margin_usdt: str | None = None


class GridReconfigureMeta(BaseModel):
    version: int
    old_params: dict[str, str]
    new_params: dict[str, str]
    direction: str
    current_price: str
    current_net_position: str
    target_net_position: str
    rebalance_side: str
    rebalance_qty: str
    cancelled_order_count: int
    submitted_order_count: int
    status: str


class GridReconfigureResult(BaseModel):
    detail: GridDetailView
    message: str
    reconfigure: GridReconfigureMeta


ContractGridCreateRequest = GridCreateRequest
ContractGridSummaryView = GridSummaryView
ContractGridStrategyView = GridStrategyView
ContractGridListView = GridListView
ContractGridOrderView = GridOrderView
ContractGridFillView = GridFillView
ContractGridEventView = GridEventView
ContractGridDetailView = GridDetailView
ContractGridActionResult = GridActionResult
ContractGridReconfigureRequest = GridReconfigureRequest
ContractGridReconfigureMeta = GridReconfigureMeta
ContractGridReconfigureResult = GridReconfigureResult
