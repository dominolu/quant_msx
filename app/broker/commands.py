from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Market = Literal["spot", "futures"]


@dataclass(frozen=True, slots=True)
class SpotOrderRequest:
    symbol: str
    side: Literal["buy", "sell"]
    type: Literal["limit", "market"]
    quantity: str
    price: str | None = None
    client_oid: str | None = None


@dataclass(frozen=True, slots=True)
class FuturesOrderRequest:
    symbol: str
    co_type: int
    order_type: Literal[1, 2]
    open_type: Literal[1, 2]
    side: Literal[1, 2]
    price: str | None = None
    vol: str | None = None
    amt: str | None = None
    leverage: str | None = None
    pos_id: int | None = None
    stop_profit_price: str | None = None
    stop_loss_price: str | None = None
    trigger_type: int | None = None


@dataclass(frozen=True, slots=True)
class CancelSpotOrderRequest:
    symbol: str
    order_id: str


@dataclass(frozen=True, slots=True)
class CancelFuturesOrderRequest:
    order_id: int


OrderRequest = SpotOrderRequest | FuturesOrderRequest
CancelOrderRequest = CancelSpotOrderRequest | CancelFuturesOrderRequest
