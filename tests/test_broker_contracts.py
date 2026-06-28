import base64
import hashlib
import hmac

from app.broker.msx_rest import MsxRestClient
from app.broker.msx_ws import (
    book_ticker_stream,
    kline_stream,
    mini_ticker_arr_stream,
    order_book_stream,
    order_book_update_stream,
    subscribe_payload,
    ticker_stream,
    unsubscribe_payload,
)


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
