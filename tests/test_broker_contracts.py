import asyncio
import base64
import hashlib
import hmac
import json

import httpx
import pytest

from app.broker.msx_rest import MsxApiError, MsxRestClient
from app.broker.msx_ws import (
    MsxWebSocketClient,
    MsxWsSubscription,
    book_ticker_stream,
    kline_stream,
    mini_ticker_arr_stream,
    order_book_stream,
    order_book_update_stream,
    subscribe_payload,
    ticker_stream,
    unsubscribe_payload,
)
from app.broker.endpoints import ENDPOINTS, endpoint
from app.broker.msx import MsxBroker
from app.broker.orderbook import LocalOrderBook, OrderBookDelta, OrderBookSnapshot


def run(coro):
    return asyncio.run(coro)


def test_sign_get_query_is_sorted() -> None:
    client = MsxRestClient(api_key="key", secret_key="secret")
    timestamp, signature = client.sign(
        "GET",
        "/api/v1/stock/open-api/depth",
        query={"symbol": "XSM", "limit": 20},
        timestamp=1705737600000,
    )
    pre_hash = "1705737600000GET/api/v1/stock/open-api/depth?limit=20&symbol=XSM"
    expected = base64.b64encode(
        hmac.new(b"secret", pre_hash.encode(), hashlib.sha256).digest()
    ).decode()
    assert timestamp == "1705737600000"
    assert signature == expected


def test_sign_post_uses_compact_json_body() -> None:
    client = MsxRestClient(api_key="key", secret_key="secret")
    body = '{"symbol":"AAPL","side":"buy","type":"limit","price":"185.50","quantity":"1000"}'
    _, signature = client.sign(
        "POST",
        "/api/v1/stock/open-api/order",
        body=body,
        timestamp=1705737600000,
    )
    pre_hash = f"1705737600000POST/api/v1/stock/open-api/order{body}"
    expected = base64.b64encode(
        hmac.new(b"secret", pre_hash.encode(), hashlib.sha256).digest()
    ).decode()
    assert signature == expected


def test_websocket_stream_builders() -> None:
    assert ticker_stream("BTCUSDT") == "BTCUSDT@ticker"
    assert book_ticker_stream("MSX") == "MSX@book_ticker"
    assert kline_stream("AAPL", "1m") == "AAPL@kline_1m"
    assert mini_ticker_arr_stream() == "!miniTicker@arr@3000ms"
    assert order_book_stream("BTCUSDT", depth=20) == "BTCUSDT@order_book20"
    assert order_book_stream("BTCUSDT", depth=20, speed="100ms") == "BTCUSDT@order_book20@100ms"
    assert order_book_update_stream("MSX") == "MSX@order_book_update"


def test_websocket_payload_builders() -> None:
    streams = ["MSX@ticker", "MSX@book_ticker"]
    assert subscribe_payload(streams) == {"action": "subscribe", "streams": streams}
    assert unsubscribe_payload(streams) == {"action": "unsubscribe", "streams": streams}


def test_spot_order_uses_spot_path_and_auth_headers() -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["path"] = request.url.path
        seen["body"] = json.loads(request.content.decode())
        seen["headers"] = dict(request.headers)
        return httpx.Response(200, json={"code": 0, "data": {"orderId": "1"}})

    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="https://example.test",
        ) as http_client:
            client = MsxRestClient(
                base_url="https://example.test",
                api_key="key",
                secret_key="secret",
                client=http_client,
            )
            await client.create_spot_order(
                symbol="AAPL",
                side="buy",
                type="limit",
                price="185.50",
                quantity="10",
                client_oid="spot-1",
            )

    run(scenario())
    assert seen["method"] == "POST"
    assert seen["path"] == "/api/v1/stock/open-api/order"
    assert seen["body"] == {
        "symbol": "AAPL",
        "side": "buy",
        "type": "limit",
        "price": "185.50",
        "quantity": "10",
        "clientOid": "spot-1",
    }
    assert seen["headers"]["access-key"] == "key"
    assert "access-sign" in seen["headers"]
    assert "access-timestamp" in seen["headers"]


def test_futures_order_uses_futures_path() -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["path"] = request.url.path
        seen["body"] = json.loads(request.content.decode())
        return httpx.Response(200, json={"code": 0, "data": {"orderId": 1}})

    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="https://example.test",
        ) as http_client:
            client = MsxRestClient(
                base_url="https://example.test",
                api_key="key",
                secret_key="secret",
                client=http_client,
            )
            await client.create_futures_order(
                symbol="BTCUSDT",
                co_type=3,
                order_type=2,
                open_type=1,
                side=1,
                amt="100",
                leverage="10",
                trigger_type=1,
            )

    run(scenario())
    assert seen["method"] == "POST"
    assert seen["path"] == "/api/v1/futures/open-api/order/create"
    assert seen["body"] == {
        "symbol": "BTCUSDT",
        "coType": 3,
        "orderType": 2,
        "openType": 1,
        "side": 1,
        "amt": "100",
        "leverage": "10",
        "triggerType": 1,
    }


def test_explicit_market_dispatch_prevents_default_spot_ordering() -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        return httpx.Response(200, json={"code": 0, "data": {}})

    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="https://example.test",
        ) as http_client:
            client = MsxRestClient(
                base_url="https://example.test",
                api_key="key",
                secret_key="secret",
                client=http_client,
            )
            await client.create_order(
                "futures",
                symbol="BTCUSDT",
                co_type=3,
                order_type=2,
                open_type=1,
                side=1,
                amt="100",
                leverage="10",
            )

    run(scenario())
    assert seen["path"] == "/api/v1/futures/open-api/order/create"


def test_public_market_data_does_not_send_auth_headers() -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["query"] = request.url.query.decode()
        seen["headers"] = dict(request.headers)
        return httpx.Response(200, json={"code": 0, "data": {}})

    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="https://example.test",
        ) as http_client:
            client = MsxRestClient(
                base_url="https://example.test",
                api_key="key",
                secret_key="secret",
                client=http_client,
            )
            await client.get_futures_orderbook(symbol="BTCUSDT", depth=20, with_id=True)

    run(scenario())
    assert seen["path"] == "/api/v1/futures/open-api/orderbook/BTCUSDT"
    assert seen["query"] == "depth=20&with_id=true"
    assert "access-key" not in seen["headers"]
    assert "access-sign" not in seen["headers"]


def test_string_zero_code_is_success() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"code": "0", "data": {"ok": True}})

    async def scenario() -> dict:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="https://example.test",
        ) as http_client:
            client = MsxRestClient(
                base_url="https://example.test",
                api_key="key",
                secret_key="secret",
                client=http_client,
            )
            return await client.get_spot_ticker(symbol="MSX")

    payload = run(scenario())
    assert payload["data"]["ok"] is True


def test_nonzero_string_code_raises_api_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"code": "8001", "msg": "too small"})

    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="https://example.test",
        ) as http_client:
            client = MsxRestClient(
                base_url="https://example.test",
                api_key="key",
                secret_key="secret",
                client=http_client,
            )
            await client.get_spot_ticker(symbol="MSX")

    with pytest.raises(MsxApiError) as exc:
        run(scenario())

    assert exc.value.code == 8001
    assert exc.value.message == "too small"


def test_websocket_subscription_market_must_match_client_market() -> None:
    client = MsxWebSocketClient(market="spot")
    subscription = MsxWsSubscription(market="futures", stream="BTCUSDT@ticker")
    with pytest.raises(ValueError):
        client._ensure_subscription_market(subscription)


def test_endpoint_registry_contains_all_current_rest_endpoints() -> None:
    expected = {
        "spot.assets",
        "spot.create_order",
        "spot.batch_create_orders",
        "spot.cancel_order",
        "spot.batch_cancel_orders",
        "spot.depth",
        "spot.klines",
        "spot.open_orders",
        "spot.history_orders",
        "spot.order_detail",
        "spot.price_steps",
        "spot.ticker",
        "spot.trades",
        "futures.account_config",
        "futures.set_leverage",
        "futures.set_margin_mode",
        "futures.klines",
        "futures.cancel_order",
        "futures.create_order",
        "futures.entrust_history",
        "futures.order_history",
        "futures.open_orders",
        "futures.orderbook",
        "futures.positions",
        "futures.position_history",
        "futures.price_steps",
        "futures.products",
        "futures.ticker",
        "legacy.products",
        "legacy.ticker_price",
        "legacy.depth",
    }
    assert expected <= set(ENDPOINTS)
    assert endpoint("futures.orderbook").path(symbol="BTCUSDT").endswith("/BTCUSDT")


def test_local_orderbook_applies_snapshot_and_delta() -> None:
    book = LocalOrderBook("BTCUSDT")
    book.apply_snapshot(
        OrderBookSnapshot(
            symbol="BTCUSDT",
            bids=[["100", "1"], ["99", "2"]],
            asks=[["101", "1"]],
            update_id=10,
        )
    )
    book.apply_delta(
        OrderBookDelta(
            symbol="BTCUSDT",
            first_update_id=11,
            last_update_id=11,
            bids=[["100", "0"], ["98", "3"]],
            asks=[["101", "2"]],
        )
    )
    assert book.top_bids() == [("99", "2"), ("98", "3")]
    assert book.top_asks() == [("101", "2")]


def test_msx_broker_facade_exposes_sub_brokers() -> None:
    rest = MsxRestClient(api_key="key", secret_key="secret")
    broker = MsxBroker(rest=rest)
    assert broker.rest is rest
    assert broker.market_data.rest is rest
    assert broker.orders.rest is rest
    assert broker.account.rest is rest


def test_msx_broker_facade_rejects_unknown_market() -> None:
    rest = MsxRestClient(api_key="key", secret_key="secret")
    broker = MsxBroker(rest=rest)

    with pytest.raises(ValueError):
        run(broker.market_data.get_ticker("bad", "BTCUSDT"))  # type: ignore[arg-type]


def test_msx_broker_close_does_not_close_injected_clients() -> None:
    class CloseRecorder:
        def __init__(self) -> None:
            self.closed = False

        async def close(self) -> None:
            self.closed = True

    rest = CloseRecorder()
    spot_ws = CloseRecorder()
    futures_ws = CloseRecorder()
    broker = MsxBroker(
        rest=rest,  # type: ignore[arg-type]
        spot_ws=spot_ws,  # type: ignore[arg-type]
        futures_ws=futures_ws,  # type: ignore[arg-type]
    )

    run(broker.close())

    assert rest.closed is False
    assert spot_ws.closed is False
    assert futures_ws.closed is False
