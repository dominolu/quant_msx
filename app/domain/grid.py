from __future__ import annotations

from pydantic import BaseModel, Field


class GridCreateRequest(BaseModel):
    name: str
    market: str = "futures"
    symbol: str
    direction: str = "neutral"
    margin_mode: str = "cross"
    leverage: str = "1"
    margin_usdt: str = "0"
    spacing_mode: str = "geometric"
    grid_spacing_pct: str = "0.5"
    grid_levels: int = 0
    order_qty: str = "0"
    max_position_qty: str = "0"
    stop_loss_price: str = "0"
    take_profit_price: str = "0"
    max_loss_usdt: str = "0"
    start_immediately: bool = False


class GridSummaryView(BaseModel):
    running_count: int = 0
    today_fill_count: int = 0
    today_grid_profit_usdt: str = "0"
    total_invested_usdt: str = "0"
    total_return_usdt: str = "0"
    websocket_status: str = "unknown"
    rest_sync_count: int = 0
    cache_updated_at: str = ""


class GridStrategyView(BaseModel):
    id: int
    grid_key: str
    name: str
    market: str
    symbol: str
    status: str
    direction: str
    margin_mode: str
    leverage: str
    grid_spacing_pct: str
    grid_levels: int
    order_qty: str
    current_price: str
    base_price: str
    lower_order_price: str
    upper_order_price: str
    current_position_qty: str
    grid_profit_usdt: str
    total_pnl_usdt: str
    health: str
    chart_points: list[float] = Field(default_factory=list)
    created_at: str
    updated_at: str


class GridListView(BaseModel):
    summary: GridSummaryView
    items: list[GridStrategyView] = Field(default_factory=list)
