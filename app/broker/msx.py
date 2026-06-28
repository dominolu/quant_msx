from __future__ import annotations

from dataclasses import asdict
from typing import Any

from app.broker.commands import (
    CancelFuturesOrderRequest,
    CancelOrderRequest,
    CancelSpotOrderRequest,
    FuturesOrderRequest,
    Market,
    OrderRequest,
    SpotOrderRequest,
)
from app.broker.msx_rest import MsxRestClient
from app.broker.msx_ws import MsxWebSocketClient


class MsxMarketDataBroker:
    def __init__(self, rest: MsxRestClient) -> None:
        self.rest = rest

    async def get_ticker(self, market: Market, symbol: str) -> Any:
        if market == "spot":
            return await self.rest.get_spot_ticker(symbol=symbol)
        if market == "futures":
            return await self.rest.get_futures_ticker(symbol=symbol)
        raise ValueError(f"Unsupported MSX market: {market}")

    async def get_orderbook(
        self,
        market: Market,
        symbol: str,
        *,
        depth: int | None = None,
        with_id: bool | None = None,
        step: str | None = None,
    ) -> Any:
        if market == "spot":
            return await self.rest.get_spot_depth(symbol=symbol, limit=depth)
        if market == "futures":
            return await self.rest.get_futures_orderbook(
                symbol=symbol,
                depth=depth,
                with_id=with_id,
                step=step,
            )
        raise ValueError(f"Unsupported MSX market: {market}")

    async def get_klines(self, market: Market, symbol: str, interval: str, **kwargs: Any) -> Any:
        if market == "spot":
            return await self.rest.get_spot_klines(symbol=symbol, interval=interval, **kwargs)
        if market == "futures":
            return await self.rest.get_futures_klines(symbol=symbol, interval=interval, **kwargs)
        raise ValueError(f"Unsupported MSX market: {market}")

    async def get_price_steps(self, market: Market, symbol: str) -> Any:
        if market == "spot":
            return await self.rest.get_spot_price_steps(symbol=symbol)
        if market == "futures":
            return await self.rest.get_futures_price_steps(symbol=symbol)
        raise ValueError(f"Unsupported MSX market: {market}")


class MsxOrderBroker:
    def __init__(self, rest: MsxRestClient) -> None:
        self.rest = rest

    async def create(self, request: OrderRequest) -> Any:
        if isinstance(request, SpotOrderRequest):
            return await self.rest.create_spot_order(**asdict(request))
        if isinstance(request, FuturesOrderRequest):
            return await self.rest.create_futures_order(**asdict(request))
        raise TypeError(f"Unsupported order request: {type(request)!r}")

    async def cancel(self, request: CancelOrderRequest) -> Any:
        if isinstance(request, CancelSpotOrderRequest):
            return await self.rest.cancel_spot_order(
                symbol=request.symbol,
                order_id=request.order_id,
            )
        if isinstance(request, CancelFuturesOrderRequest):
            return await self.rest.cancel_futures_order(order_id=request.order_id)
        raise TypeError(f"Unsupported cancel request: {type(request)!r}")

    async def get_open_orders(self, market: Market, **kwargs: Any) -> Any:
        if market == "spot":
            return await self.rest.get_spot_open_orders(**kwargs)
        if market == "futures":
            return await self.rest.get_futures_open_orders(**kwargs)
        raise ValueError(f"Unsupported MSX market: {market}")


class MsxAccountBroker:
    def __init__(self, rest: MsxRestClient) -> None:
        self.rest = rest

    async def get_assets(self, symbol: str | None = None) -> Any:
        return await self.rest.get_spot_assets(symbol=symbol)

    async def get_positions(self, **kwargs: Any) -> Any:
        return await self.rest.get_futures_positions(**kwargs)

    async def get_futures_config(self, symbol: str) -> Any:
        return await self.rest.get_futures_account_config(symbol=symbol)


class MsxBroker:
    def __init__(
        self,
        *,
        rest: MsxRestClient | None = None,
        spot_ws: MsxWebSocketClient | None = None,
        futures_ws: MsxWebSocketClient | None = None,
    ) -> None:
        self._owns_rest = rest is None
        self._owns_spot_ws = spot_ws is None
        self._owns_futures_ws = futures_ws is None
        self.rest = rest or MsxRestClient()
        self.market_data = MsxMarketDataBroker(self.rest)
        self.orders = MsxOrderBroker(self.rest)
        self.account = MsxAccountBroker(self.rest)
        self.spot_ws = spot_ws or MsxWebSocketClient(market="spot")
        self.futures_ws = futures_ws or MsxWebSocketClient(market="futures")

    async def close(self) -> None:
        if self._owns_rest:
            await self.rest.close()
        if self._owns_spot_ws:
            await self.spot_ws.close()
        if self._owns_futures_ws:
            await self.futures_ws.close()
