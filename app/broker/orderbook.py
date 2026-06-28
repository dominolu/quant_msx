from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class OrderBookSnapshot:
    symbol: str
    bids: list[list[str]]
    asks: list[list[str]]
    update_id: int | None = None


@dataclass(slots=True)
class OrderBookDelta:
    symbol: str
    first_update_id: int
    last_update_id: int
    bids: list[list[str]]
    asks: list[list[str]]


@dataclass(slots=True)
class LocalOrderBook:
    symbol: str
    bids: dict[str, str] = field(default_factory=dict)
    asks: dict[str, str] = field(default_factory=dict)
    last_update_id: int | None = None

    def apply_snapshot(self, snapshot: OrderBookSnapshot) -> None:
        if snapshot.symbol != self.symbol:
            raise ValueError(f"Snapshot symbol {snapshot.symbol} does not match {self.symbol}")
        self.bids = {price: qty for price, qty in snapshot.bids}
        self.asks = {price: qty for price, qty in snapshot.asks}
        self.last_update_id = snapshot.update_id

    def apply_delta(self, delta: OrderBookDelta, *, strict: bool = True) -> None:
        if delta.symbol != self.symbol:
            raise ValueError(f"Delta symbol {delta.symbol} does not match {self.symbol}")
        if strict and self.last_update_id is not None:
            expected = self.last_update_id + 1
            if delta.first_update_id > expected or delta.last_update_id < expected:
                raise ValueError(
                    f"Order book sequence gap for {self.symbol}: "
                    f"expected {expected}, got {delta.first_update_id}-{delta.last_update_id}"
                )
        self._apply_side(self.bids, delta.bids)
        self._apply_side(self.asks, delta.asks)
        self.last_update_id = delta.last_update_id

    def top_bids(self, limit: int = 20) -> list[tuple[str, str]]:
        return sorted(self.bids.items(), key=lambda item: float(item[0]), reverse=True)[:limit]

    def top_asks(self, limit: int = 20) -> list[tuple[str, str]]:
        return sorted(self.asks.items(), key=lambda item: float(item[0]))[:limit]

    @staticmethod
    def _apply_side(book: dict[str, str], changes: list[list[str]]) -> None:
        for price, qty in changes:
            if qty == "0":
                book.pop(price, None)
            else:
                book[price] = qty
