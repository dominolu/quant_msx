from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.broker.common import HttpMethod, Market

EndpointScope = Literal["spot", "futures", "legacy"]

SPOT_PREFIX = "/api/v1/stock/open-api"
FUTURES_PREFIX = "/api/v1/futures/open-api"
LEGACY_FDATA_PREFIX = "/api/v1/fdata"


@dataclass(frozen=True, slots=True)
class Endpoint:
    name: str
    method: HttpMethod
    path_template: str
    auth: bool
    scope: EndpointScope

    def path(self, **path_params: object) -> str:
        return self.path_template.format(**path_params)


ENDPOINTS: dict[str, Endpoint] = {
    "spot.assets": Endpoint("spot.assets", "GET", f"{SPOT_PREFIX}/assets", True, "spot"),
    "spot.create_order": Endpoint(
        "spot.create_order", "POST", f"{SPOT_PREFIX}/order", True, "spot"
    ),
    "spot.batch_create_orders": Endpoint(
        "spot.batch_create_orders", "POST", f"{SPOT_PREFIX}/batchOrder", True, "spot"
    ),
    "spot.cancel_order": Endpoint(
        "spot.cancel_order", "POST", f"{SPOT_PREFIX}/cancelOrder", True, "spot"
    ),
    "spot.batch_cancel_orders": Endpoint(
        "spot.batch_cancel_orders", "POST", f"{SPOT_PREFIX}/batchCancelOrder", True, "spot"
    ),
    "spot.depth": Endpoint("spot.depth", "GET", f"{SPOT_PREFIX}/depth", False, "spot"),
    "spot.klines": Endpoint("spot.klines", "GET", f"{SPOT_PREFIX}/klines", False, "spot"),
    "spot.open_orders": Endpoint(
        "spot.open_orders", "GET", f"{SPOT_PREFIX}/openOrders", True, "spot"
    ),
    "spot.history_orders": Endpoint(
        "spot.history_orders", "GET", f"{SPOT_PREFIX}/historyOrders", True, "spot"
    ),
    "spot.order_detail": Endpoint(
        "spot.order_detail", "GET", f"{SPOT_PREFIX}/orderDetail", True, "spot"
    ),
    "spot.price_steps": Endpoint(
        "spot.price_steps", "GET", f"{SPOT_PREFIX}/priceSteps", False, "spot"
    ),
    "spot.ticker": Endpoint("spot.ticker", "GET", f"{SPOT_PREFIX}/ticker", False, "spot"),
    "spot.trades": Endpoint("spot.trades", "GET", f"{SPOT_PREFIX}/trades", True, "spot"),
    "futures.account_config": Endpoint(
        "futures.account_config", "GET", f"{FUTURES_PREFIX}/account/config", True, "futures"
    ),
    "futures.set_leverage": Endpoint(
        "futures.set_leverage", "POST", f"{FUTURES_PREFIX}/account/leverage", True, "futures"
    ),
    "futures.set_margin_mode": Endpoint(
        "futures.set_margin_mode",
        "POST",
        f"{FUTURES_PREFIX}/account/margin-mode",
        True,
        "futures",
    ),
    "futures.klines": Endpoint(
        "futures.klines", "GET", f"{FUTURES_PREFIX}/kline", False, "futures"
    ),
    "futures.cancel_order": Endpoint(
        "futures.cancel_order", "POST", f"{FUTURES_PREFIX}/order/cancel", True, "futures"
    ),
    "futures.create_order": Endpoint(
        "futures.create_order", "POST", f"{FUTURES_PREFIX}/order/create", True, "futures"
    ),
    "futures.entrust_history": Endpoint(
        "futures.entrust_history",
        "POST",
        f"{FUTURES_PREFIX}/order/entrust-history",
        True,
        "futures",
    ),
    "futures.order_history": Endpoint(
        "futures.order_history", "POST", f"{FUTURES_PREFIX}/order/history", True, "futures"
    ),
    "futures.open_orders": Endpoint(
        "futures.open_orders", "POST", f"{FUTURES_PREFIX}/order/limit", True, "futures"
    ),
    "futures.orderbook": Endpoint(
        "futures.orderbook",
        "GET",
        f"{FUTURES_PREFIX}/orderbook/{{symbol}}",
        False,
        "futures",
    ),
    "futures.positions": Endpoint(
        "futures.positions", "POST", f"{FUTURES_PREFIX}/position/current", True, "futures"
    ),
    "futures.position_history": Endpoint(
        "futures.position_history",
        "POST",
        f"{FUTURES_PREFIX}/position/history",
        True,
        "futures",
    ),
    "futures.price_steps": Endpoint(
        "futures.price_steps",
        "GET",
        f"{FUTURES_PREFIX}/price-steps/{{symbol}}",
        False,
        "futures",
    ),
    "futures.products": Endpoint(
        "futures.products", "GET", f"{FUTURES_PREFIX}/products", False, "futures"
    ),
    "futures.ticker": Endpoint(
        "futures.ticker", "GET", f"{FUTURES_PREFIX}/ticker/{{symbol}}", False, "futures"
    ),
    "legacy.products": Endpoint(
        "legacy.products", "GET", f"{LEGACY_FDATA_PREFIX}/productList", False, "legacy"
    ),
    "legacy.ticker_price": Endpoint(
        "legacy.ticker_price", "GET", f"{LEGACY_FDATA_PREFIX}/ticker/price", False, "legacy"
    ),
    "legacy.depth": Endpoint(
        "legacy.depth", "GET", f"{LEGACY_FDATA_PREFIX}/depth", False, "legacy"
    ),
}


def endpoint(name: str) -> Endpoint:
    return ENDPOINTS[name]


def endpoint_for_order(market: Market, action: Literal["create", "cancel"]) -> Endpoint:
    return endpoint(f"{market}.{'create_order' if action == 'create' else 'cancel_order'}")
