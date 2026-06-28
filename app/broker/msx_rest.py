from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import urlencode

import httpx

from app.core.config import settings

JsonDict = dict[str, Any]
HttpMethod = Literal["GET", "POST"]


class MsxRestError(Exception):
    """Base class for MSX REST errors."""


@dataclass(slots=True)
class MsxHttpError(MsxRestError):
    status_code: int
    method: str
    path: str
    body: Any

    def __str__(self) -> str:
        return f"MSX HTTP {self.status_code} for {self.method} {self.path}: {self.body}"


@dataclass(slots=True)
class MsxApiError(MsxRestError):
    code: int
    message: str
    method: str
    path: str
    payload: JsonDict

    def __str__(self) -> str:
        return f"MSX API code={self.code} for {self.method} {self.path}: {self.message}"


def _drop_none(params: JsonDict | None) -> JsonDict:
    return {key: value for key, value in (params or {}).items() if value is not None}


def _query_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _json_body(data: JsonDict | list[Any] | None) -> str:
    if data is None:
        return ""
    return json.dumps(data, separators=(",", ":"), ensure_ascii=False)


class MsxRestClient:
    """MSX REST broker client.

    The client covers every REST endpoint currently summarized in docs/api.md:
    spot Open API, futures Open API, and legacy V1 derivatives market-data API.
    Methods return the raw JSON payload so service/domain layers can decide how
    to normalize data for strategies.
    """

    SPOT_PREFIX = "/api/v1/stock/open-api"
    FUTURES_PREFIX = "/api/v1/futures/open-api"
    LEGACY_FDATA_PREFIX = "/api/v1/fdata"

    def __init__(
        self,
        base_url: str | None = None,
        *,
        api_key: str | None = None,
        secret_key: str | None = None,
        timeout: float = 30.0,
        client: httpx.AsyncClient | None = None,
        raise_api_errors: bool = True,
    ) -> None:
        self.base_url = (base_url or settings.msx_base_url).rstrip("/")
        self.api_key = settings.msx_api_key if api_key is None else api_key
        self.secret_key = settings.msx_secret_key if secret_key is None else secret_key
        self.raise_api_errors = raise_api_errors
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(timeout=timeout)

    async def __aenter__(self) -> MsxRestClient:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.close()

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    def sign(
        self,
        method: str,
        request_path: str,
        *,
        query: JsonDict | None = None,
        body: str = "",
        timestamp: int | None = None,
    ) -> tuple[str, str]:
        ts = str(timestamp or int(time.time() * 1000))
        query_string = self.build_query_string(query)
        payload = f"{ts}{method.upper()}{request_path}{query_string}{body}"
        digest = hmac.new(self.secret_key.encode(), payload.encode(), hashlib.sha256).digest()
        return ts, base64.b64encode(digest).decode()

    @staticmethod
    def build_query_string(query: JsonDict | None) -> str:
        params = _drop_none(query)
        if not params:
            return ""
        sorted_items = [(key, _query_value(params[key])) for key in sorted(params)]
        return "?" + urlencode(sorted_items)

    def _auth_headers(
        self,
        method: str,
        path: str,
        *,
        query: JsonDict | None,
        body: str,
    ) -> JsonDict:
        if not self.api_key or not self.secret_key:
            raise ValueError("MSX API key and secret key are required for authenticated requests")
        timestamp, signature = self.sign(method, path, query=query, body=body)
        return {
            "ACCESS-KEY": self.api_key,
            "ACCESS-SIGN": signature,
            "ACCESS-TIMESTAMP": timestamp,
        }

    async def request(
        self,
        method: HttpMethod,
        path: str,
        *,
        query: JsonDict | None = None,
        body: JsonDict | list[Any] | None = None,
        auth: bool = True,
    ) -> Any:
        method = method.upper()  # type: ignore[assignment]
        params = _drop_none(query)
        raw_body = _json_body(body) if method == "POST" else ""
        headers: JsonDict = {}
        if method == "POST":
            headers["Content-Type"] = "application/json"
        if auth:
            headers.update(self._auth_headers(method, path, query=params, body=raw_body))

        response = await self._client.request(
            method,
            f"{self.base_url}{path}",
            params=[(key, _query_value(params[key])) for key in sorted(params)] or None,
            content=raw_body.encode("utf-8") if raw_body else None,
            headers=headers,
        )

        try:
            payload: Any = response.json()
        except ValueError:
            payload = response.text

        if response.status_code >= 400:
            raise MsxHttpError(response.status_code, method, path, payload)

        if self.raise_api_errors and isinstance(payload, dict):
            code = payload.get("code")
            if code not in (None, 0):
                message = str(
                    payload.get("msg") or payload.get("message") or payload.get("error") or ""
                )
                raise MsxApiError(int(code), message, method, path, payload)

        return payload

    async def get(self, path: str, *, query: JsonDict | None = None, auth: bool = True) -> Any:
        return await self.request("GET", path, query=query, auth=auth)

    async def post(self, path: str, *, body: JsonDict | list[Any] | None = None) -> Any:
        return await self.request("POST", path, body=body, auth=True)

    # Spot REST endpoints -------------------------------------------------

    async def get_spot_assets(self, symbol: str | None = None) -> Any:
        return await self.get(f"{self.SPOT_PREFIX}/assets", query={"symbol": symbol}, auth=True)

    async def create_spot_order(
        self,
        *,
        symbol: str,
        side: Literal["buy", "sell"],
        type: Literal["limit", "market"],
        quantity: str,
        price: str | None = None,
        client_oid: str | None = None,
        **extra: Any,
    ) -> Any:
        body = {
            "symbol": symbol,
            "side": side,
            "type": type,
            "price": price,
            "quantity": quantity,
            "clientOid": client_oid,
            **extra,
        }
        return await self.post(f"{self.SPOT_PREFIX}/order", body=_drop_none(body))

    async def batch_create_spot_orders(self, orders: list[JsonDict]) -> Any:
        return await self.post(f"{self.SPOT_PREFIX}/batchOrder", body={"orders": orders})

    async def cancel_spot_order(self, *, symbol: str, order_id: str) -> Any:
        return await self.post(
            f"{self.SPOT_PREFIX}/cancelOrder",
            body={"symbol": symbol, "orderId": order_id},
        )

    async def batch_cancel_spot_orders(self, *, symbol: str, order_ids: list[str]) -> Any:
        return await self.post(
            f"{self.SPOT_PREFIX}/batchCancelOrder",
            body={"symbol": symbol, "orderIds": order_ids},
        )

    async def get_spot_depth(self, *, symbol: str, limit: int | None = None) -> Any:
        return await self.get(
            f"{self.SPOT_PREFIX}/depth",
            query={"symbol": symbol, "limit": limit},
            auth=False,
        )

    async def get_spot_klines(
        self,
        *,
        symbol: str,
        interval: str,
        start_time: int | None = None,
        end_time: int | None = None,
        limit: int | None = None,
    ) -> Any:
        return await self.get(
            f"{self.SPOT_PREFIX}/klines",
            query={
                "symbol": symbol,
                "interval": interval,
                "startTime": start_time,
                "endTime": end_time,
                "limit": limit,
            },
            auth=False,
        )

    async def get_spot_open_orders(
        self,
        *,
        symbol: str | None = None,
        side: Literal["buy", "sell"] | None = None,
        page: int | None = None,
        size: int | None = None,
    ) -> Any:
        return await self.get(
            f"{self.SPOT_PREFIX}/openOrders",
            query={"symbol": symbol, "side": side, "page": page, "size": size},
            auth=True,
        )

    async def get_spot_history_orders(
        self,
        *,
        symbol: str | None = None,
        side: Literal["buy", "sell"] | None = None,
        start_time: int | None = None,
        end_time: int | None = None,
        page: int | None = None,
        size: int | None = None,
    ) -> Any:
        return await self.get(
            f"{self.SPOT_PREFIX}/historyOrders",
            query={
                "symbol": symbol,
                "side": side,
                "startTime": start_time,
                "endTime": end_time,
                "page": page,
                "size": size,
            },
            auth=True,
        )

    async def get_spot_order_detail(self, *, symbol: str, order_id: str) -> Any:
        return await self.get(
            f"{self.SPOT_PREFIX}/orderDetail",
            query={"symbol": symbol, "orderId": order_id},
            auth=True,
        )

    async def get_spot_price_steps(self, *, symbol: str) -> Any:
        return await self.get(
            f"{self.SPOT_PREFIX}/priceSteps",
            query={"symbol": symbol},
            auth=False,
        )

    async def get_spot_ticker(self, *, symbol: str) -> Any:
        return await self.get(f"{self.SPOT_PREFIX}/ticker", query={"symbol": symbol}, auth=False)

    async def get_spot_trades(
        self,
        *,
        symbol: str | None = None,
        order_id: str | None = None,
        start_time: int | None = None,
        end_time: int | None = None,
        page: int | None = None,
        size: int | None = None,
    ) -> Any:
        return await self.get(
            f"{self.SPOT_PREFIX}/trades",
            query={
                "symbol": symbol,
                "orderId": order_id,
                "startTime": start_time,
                "endTime": end_time,
                "page": page,
                "size": size,
            },
            auth=True,
        )

    # Futures REST endpoints ---------------------------------------------

    async def get_futures_account_config(self, *, symbol: str) -> Any:
        return await self.get(
            f"{self.FUTURES_PREFIX}/account/config",
            query={"symbol": symbol},
            auth=True,
        )

    async def set_futures_leverage(
        self,
        *,
        symbol: str,
        leverage: str,
        margin_mode: Literal[1, 2],
    ) -> Any:
        return await self.post(
            f"{self.FUTURES_PREFIX}/account/leverage",
            body={"symbol": symbol, "leverage": leverage, "marginMode": margin_mode},
        )

    async def set_futures_margin_mode(self, *, symbol: str, margin_mode: Literal[1, 2]) -> Any:
        return await self.post(
            f"{self.FUTURES_PREFIX}/account/margin-mode",
            body={"symbol": symbol, "marginMode": margin_mode},
        )

    async def get_futures_klines(
        self,
        *,
        symbol: str,
        interval: str | None = None,
        start_time: int | None = None,
        end_time: int | None = None,
        limit: int | None = None,
    ) -> Any:
        return await self.get(
            f"{self.FUTURES_PREFIX}/kline",
            query={
                "symbol": symbol,
                "interval": interval,
                "startTime": start_time,
                "endTime": end_time,
                "limit": limit,
            },
            auth=False,
        )

    async def cancel_futures_order(self, *, order_id: int) -> Any:
        return await self.post(f"{self.FUTURES_PREFIX}/order/cancel", body={"orderId": order_id})

    async def create_futures_order(
        self,
        *,
        symbol: str,
        co_type: int,
        order_type: Literal[1, 2],
        open_type: Literal[1, 2],
        side: Literal[1, 2],
        price: str | None = None,
        vol: str | None = None,
        amt: str | None = None,
        leverage: str | None = None,
        pos_id: int | None = None,
        stop_profit_price: str | None = None,
        stop_loss_price: str | None = None,
        trigger_type: int | None = None,
        **extra: Any,
    ) -> Any:
        body = {
            "symbol": symbol,
            "coType": co_type,
            "orderType": order_type,
            "openType": open_type,
            "side": side,
            "price": price,
            "vol": vol,
            "amt": amt,
            "leverage": leverage,
            "posId": pos_id,
            "stopProfitPrice": stop_profit_price,
            "stopLossPrice": stop_loss_price,
            "triggerType": trigger_type,
            **extra,
        }
        return await self.post(f"{self.FUTURES_PREFIX}/order/create", body=_drop_none(body))

    async def get_futures_entrust_history(
        self,
        *,
        symbol: str | None = None,
        co_type: int | None = None,
        status: int | None = None,
        open_flag: int | None = None,
        long_flag: int | None = None,
        start_time: int | None = None,
        end_time: int | None = None,
        page_index: int | None = None,
        page_size: int | None = None,
    ) -> Any:
        return await self.post(
            f"{self.FUTURES_PREFIX}/order/entrust-history",
            body=_drop_none(
                {
                    "symbol": symbol,
                    "coType": co_type,
                    "status": status,
                    "openFlag": open_flag,
                    "longFlag": long_flag,
                    "startTime": start_time,
                    "endTime": end_time,
                    "pageIndex": page_index,
                    "pageSize": page_size,
                }
            ),
        )

    async def get_futures_order_history(
        self,
        *,
        symbol: str | None = None,
        co_type: int | None = None,
        page_index: int | None = None,
        page_size: int | None = None,
    ) -> Any:
        return await self.post(
            f"{self.FUTURES_PREFIX}/order/history",
            body=_drop_none(
                {
                    "symbol": symbol,
                    "coType": co_type,
                    "pageIndex": page_index,
                    "pageSize": page_size,
                }
            ),
        )

    async def get_futures_open_orders(
        self,
        *,
        symbol: str | None = None,
        co_type: int | None = None,
        page_index: int | None = None,
        page_size: int | None = None,
    ) -> Any:
        return await self.post(
            f"{self.FUTURES_PREFIX}/order/limit",
            body=_drop_none(
                {
                    "symbol": symbol,
                    "coType": co_type,
                    "pageIndex": page_index,
                    "pageSize": page_size,
                }
            ),
        )

    async def get_futures_orderbook(
        self,
        *,
        symbol: str,
        depth: int | None = None,
        with_id: bool | None = None,
        step: str | None = None,
    ) -> Any:
        return await self.get(
            f"{self.FUTURES_PREFIX}/orderbook/{symbol}",
            query={"depth": depth, "with_id": with_id, "step": step},
            auth=False,
        )

    async def get_futures_positions(
        self,
        *,
        symbol: str | None = None,
        co_type: int | None = None,
    ) -> Any:
        return await self.post(
            f"{self.FUTURES_PREFIX}/position/current",
            body=_drop_none({"symbol": symbol, "coType": co_type}),
        )

    async def get_futures_position_history(
        self,
        *,
        symbol: str | None = None,
        co_type: int | None = None,
        page_index: int | None = None,
        page_size: int | None = None,
    ) -> Any:
        return await self.post(
            f"{self.FUTURES_PREFIX}/position/history",
            body=_drop_none(
                {
                    "symbol": symbol,
                    "coType": co_type,
                    "pageIndex": page_index,
                    "pageSize": page_size,
                }
            ),
        )

    async def get_futures_price_steps(self, *, symbol: str) -> Any:
        return await self.get(f"{self.FUTURES_PREFIX}/price-steps/{symbol}", auth=False)

    async def get_futures_products(self, type: int | None = None) -> Any:
        return await self.get(
            f"{self.FUTURES_PREFIX}/products",
            query={"type": type},
            auth=False,
        )

    async def get_futures_ticker(self, *, symbol: str) -> Any:
        return await self.get(f"{self.FUTURES_PREFIX}/ticker/{symbol}", auth=False)

    # Legacy V1 derivatives endpoints ------------------------------------

    async def get_legacy_derivatives_products(self) -> Any:
        return await self.get(f"{self.LEGACY_FDATA_PREFIX}/productList", auth=False)

    async def get_legacy_derivatives_ticker_price(self, *, symbol: str) -> Any:
        return await self.get(
            f"{self.LEGACY_FDATA_PREFIX}/ticker/price",
            query={"symbol": symbol},
            auth=False,
        )

    async def get_legacy_derivatives_depth(
        self,
        *,
        symbol: str,
        limit: int | None = None,
    ) -> Any:
        return await self.get(
            f"{self.LEGACY_FDATA_PREFIX}/depth",
            query={"symbol": symbol, "limit": limit},
            auth=False,
        )

    # Common aliases used by services -------------------------------------

    create_order = create_spot_order
    cancel_order = cancel_spot_order
    get_depth = get_spot_depth
    get_klines = get_spot_klines
