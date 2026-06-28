from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

OrderMarket = Literal["spot", "futures"]
OrderSide = Literal["buy", "sell"]
OrderType = Literal["limit", "market"]
SYMBOL_PATTERN = re.compile(r"^[A-Z0-9_/-]{2,40}$")
OrderStatus = Literal[
    "pending",
    "open",
    "partially_filled",
    "filled",
    "canceled",
    "rejected",
    "failed",
    "simulated",
]


class OrderSubmitRequest(BaseModel):
    account_id: int | None = None
    source: str = "manual"
    source_id: int | None = None
    market: OrderMarket = "futures"
    symbol: str
    side: OrderSide
    order_type: OrderType = "limit"
    price: str = "0"
    qty: str = "0"
    leverage: str = "1"
    reduce_only: bool = False
    client_order_id: str = ""

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not SYMBOL_PATTERN.fullmatch(normalized):
            raise ValueError("symbol must use 2-40 uppercase letters, digits, _, /, or -")
        return normalized


class OrderCancelRequest(BaseModel):
    account_id: int | None = None
    market: OrderMarket = "futures"
    symbol: str
    order_id: str


class OrderView(BaseModel):
    id: int
    account_id: int | None = None
    source: str
    source_id: int | None = None
    market: str
    symbol: str
    side: str
    order_type: str
    price: str
    qty: str
    filled_qty: str
    avg_fill_price: str
    status: str
    client_order_id: str
    exchange_order_id: str
    live: bool
    error_message: str = ""
    raw_response: dict[str, object] = Field(default_factory=dict)
    created_at: str
    updated_at: str


class OrderListView(BaseModel):
    items: list[OrderView] = Field(default_factory=list)
