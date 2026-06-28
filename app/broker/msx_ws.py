from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Literal

import websockets
from websockets.asyncio.client import ClientConnection

from app.core.config import settings

Market = Literal["spot", "futures"]
WsAction = Literal["subscribe", "unsubscribe"]


@dataclass(slots=True)
class MsxWsSubscription:
    market: Market
    stream: str
    symbol: str | None = None


@dataclass(slots=True)
class MsxWsStatus:
    market: Market
    url: str
    connected: bool = False
    subscriptions: set[str] = field(default_factory=set)


class MsxWebSocketClient:
    """MSX public WebSocket broker client.

    Covers the stream formats documented in docs/api.md for both spot and
    futures: ticker, book_ticker, kline, miniTicker array, order_book snapshots,
    and order_book_update.
    """

    def __init__(
        self,
        market: Market = "spot",
        *,
        url: str | None = None,
        ping_interval_seconds: int = 20,
        reconnect: bool = True,
    ) -> None:
        self.market = market
        self.url = url or self.default_url(market)
        self.ping_interval_seconds = ping_interval_seconds
        self.reconnect = reconnect
        self.status = MsxWsStatus(market=market, url=self.url)
        self._ws: ClientConnection | None = None
        self._ping_task: asyncio.Task[None] | None = None

    async def __aenter__(self) -> MsxWebSocketClient:
        await self.connect()
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.close()

    @staticmethod
    def default_url(market: Market) -> str:
        if market == "spot":
            return settings.msx_spot_ws_url
        if market == "futures":
            return settings.msx_futures_ws_url
        raise ValueError(f"Unsupported MSX market: {market}")

    async def connect(self) -> None:
        if self._ws is not None:
            return
        self._ws = await websockets.connect(self.url)
        self.status.connected = True
        self._ping_task = asyncio.create_task(self._heartbeat_loop())
        if self.status.subscriptions:
            await self.subscribe_streams(sorted(self.status.subscriptions))

    async def close(self) -> None:
        if self._ping_task is not None:
            self._ping_task.cancel()
            try:
                await self._ping_task
            except asyncio.CancelledError:
                pass
            self._ping_task = None
        if self._ws is not None:
            await self._ws.close()
            self._ws = None
        self.status.connected = False

    async def _heartbeat_loop(self) -> None:
        while True:
            await asyncio.sleep(self.ping_interval_seconds)
            try:
                await self.ping()
            except Exception:
                if not self.reconnect:
                    raise
                await self._reconnect()

    async def _reconnect(self) -> None:
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:
                pass
        self._ws = None
        self.status.connected = False
        await self.connect()

    async def _send(self, payload: dict[str, Any]) -> None:
        if self._ws is None:
            await self.connect()
        assert self._ws is not None
        await self._ws.send(json.dumps(payload, separators=(",", ":"), ensure_ascii=False))

    async def recv(self) -> Any:
        if self._ws is None:
            await self.connect()
        assert self._ws is not None
        while True:
            try:
                message = await self._ws.recv()
                if isinstance(message, bytes):
                    message = message.decode("utf-8")
                return json.loads(message)
            except websockets.ConnectionClosed:
                if not self.reconnect:
                    raise
                await self._reconnect()

    async def messages(self) -> AsyncIterator[Any]:
        while True:
            yield await self.recv()

    def __aiter__(self) -> AsyncIterator[Any]:
        return self.messages()

    async def ping(self) -> None:
        await self._send({"action": "ping"})

    async def subscribe(self, subscription: MsxWsSubscription) -> None:
        await self.subscribe_streams([subscription.stream])

    async def unsubscribe(self, subscription: MsxWsSubscription) -> None:
        await self.unsubscribe_streams([subscription.stream])

    async def subscribe_streams(self, streams: list[str]) -> None:
        await self._stream_action("subscribe", streams)
        self.status.subscriptions.update(streams)

    async def unsubscribe_streams(self, streams: list[str]) -> None:
        await self._stream_action("unsubscribe", streams)
        for stream in streams:
            self.status.subscriptions.discard(stream)

    async def _stream_action(self, action: WsAction, streams: list[str]) -> None:
        if not streams:
            return
        await self._send({"action": action, "streams": streams})

    async def subscribe_ticker(self, symbol: str) -> None:
        await self.subscribe_streams([ticker_stream(symbol)])

    async def subscribe_book_ticker(self, symbol: str) -> None:
        await self.subscribe_streams([book_ticker_stream(symbol)])

    async def subscribe_kline(self, symbol: str, interval: str) -> None:
        await self.subscribe_streams([kline_stream(symbol, interval)])

    async def subscribe_mini_ticker_arr(self) -> None:
        await self.subscribe_streams([mini_ticker_arr_stream()])

    async def subscribe_order_book(
        self,
        symbol: str,
        *,
        depth: Literal[5, 10, 20, 50, 100] = 20,
        speed: Literal["100ms", "1000ms"] | None = None,
    ) -> None:
        await self.subscribe_streams([order_book_stream(symbol, depth=depth, speed=speed)])

    async def subscribe_order_book_update(self, symbol: str) -> None:
        await self.subscribe_streams([order_book_update_stream(symbol)])

    async def subscribe_mark_price(self, symbol: str) -> None:
        await self.subscribe_streams([mark_price_stream(symbol)])


def ticker_stream(symbol: str) -> str:
    return f"{symbol}@ticker"


def book_ticker_stream(symbol: str) -> str:
    return f"{symbol}@book_ticker"


def kline_stream(symbol: str, interval: str) -> str:
    return f"{symbol}@kline_{interval}"


def mini_ticker_arr_stream() -> str:
    return "!miniTicker@arr@3000ms"


def order_book_stream(
    symbol: str,
    *,
    depth: Literal[5, 10, 20, 50, 100] = 20,
    speed: Literal["100ms", "1000ms"] | None = None,
) -> str:
    stream = f"{symbol}@order_book{depth}"
    if speed:
        stream = f"{stream}@{speed}"
    return stream


def order_book_update_stream(symbol: str) -> str:
    return f"{symbol}@order_book_update"


def mark_price_stream(symbol: str) -> str:
    return f"{symbol}@markPrice"


def subscribe_payload(streams: list[str]) -> dict[str, Any]:
    return {"action": "subscribe", "streams": streams}


def unsubscribe_payload(streams: list[str]) -> dict[str, Any]:
    return {"action": "unsubscribe", "streams": streams}
