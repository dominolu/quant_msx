from __future__ import annotations

from dataclasses import dataclass, field

from app.broker.common import Market
from app.broker.msx_ws import MsxWebSocketClient


@dataclass(slots=True)
class SubscriptionState:
    market: Market
    streams: set[str] = field(default_factory=set)


class WsSubscriptionManager:
    """Keeps desired subscriptions separate from socket lifecycle."""

    def __init__(self, client: MsxWebSocketClient) -> None:
        self.client = client
        self.state = SubscriptionState(market=client.market)

    async def subscribe(self, *streams: str) -> None:
        new_streams = [stream for stream in streams if stream not in self.state.streams]
        if not new_streams:
            return
        await self.client.subscribe_streams(new_streams)
        self.state.streams.update(new_streams)

    async def unsubscribe(self, *streams: str) -> None:
        old_streams = [stream for stream in streams if stream in self.state.streams]
        if not old_streams:
            return
        await self.client.unsubscribe_streams(old_streams)
        for stream in old_streams:
            self.state.streams.discard(stream)

    async def restore(self) -> None:
        if self.state.streams:
            await self.client.subscribe_streams(sorted(self.state.streams))
