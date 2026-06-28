from __future__ import annotations

from typing import Any, Literal

import httpx

from app.broker.auth import MsxCredentials, MsxSigner
from app.broker.common import (
    HttpMethod,
    JsonDict,
    Market,
    MsxApiError,
    MsxAuthError,
    MsxHttpError,
    MsxRestError,
    build_query_string,
    drop_none,
    json_body,
    normalize_error_code,
)
from app.broker.endpoints import (
    FUTURES_PREFIX,
    LEGACY_FDATA_PREFIX,
    SPOT_PREFIX,
    Endpoint,
    endpoint,
)
from app.broker.transport import AsyncRateLimiter, HttpTransport, RetryConfig
from app.core.config import settings


class MsxRestClient:
    """MSX REST broker client.

    Public methods are intentionally kept compatible with the original broker
    facade, while execution is endpoint-table driven internally.
    """

    SPOT_PREFIX = SPOT_PREFIX
    FUTURES_PREFIX = FUTURES_PREFIX
    LEGACY_FDATA_PREFIX = LEGACY_FDATA_PREFIX

    def __init__(
        self,
        base_url: str | None = None,
        *,
        api_key: str | None = None,
        secret_key: str | None = None,
        timeout: float | None = None,
        client: httpx.AsyncClient | None = None,
        raise_api_errors: bool = True,
        retry: RetryConfig | None = None,
        rate_limiter: AsyncRateLimiter | None = None,
        max_connections: int | None = None,
        max_keepalive_connections: int | None = None,
    ) -> None:
        credentials = MsxCredentials(
            api_key=settings.msx_api_key if api_key is None else api_key,
            secret_key=settings.msx_secret_key if secret_key is None else secret_key,
        )
        self.base_url = (base_url or settings.msx_base_url).rstrip("/")
        self.credentials = credentials
        self.signer = MsxSigner(credentials)
        self.raise_api_errors = raise_api_errors
        self.transport = HttpTransport(
            self.base_url,
            timeout=timeout or settings.msx_http_timeout_seconds,
            client=client,
            retry=retry
            or RetryConfig(
                attempts=settings.msx_http_retry_attempts,
                backoff_seconds=settings.msx_http_retry_backoff_seconds,
            ),
            rate_limiter=rate_limiter
            or AsyncRateLimiter(settings.msx_http_requests_per_second or None),
            max_connections=max_connections or settings.msx_http_max_connections,
            max_keepalive_connections=(
                max_keepalive_connections or settings.msx_http_max_keepalive_connections
            ),
        )

    async def __aenter__(self) -> MsxRestClient:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.close()

    async def close(self) -> None:
        await self.transport.close()

    def sign(
        self,
        method: str,
        request_path: str,
        *,
        query: JsonDict | None = None,
        body: str = "",
        timestamp: int | None = None,
    ) -> tuple[str, str]:
        return self.signer.sign(method, request_path, query=query, body=body, timestamp=timestamp)

    @staticmethod
    def build_query_string(query: JsonDict | None) -> str:
        return build_query_string(query)

    def _auth_headers(
        self,
        method: str,
        path: str,
        *,
        query: JsonDict | None,
        body: str,
    ) -> JsonDict:
        if not self.credentials.configured:
            raise MsxAuthError("MSX API key and secret key are required for authenticated requests")
        return self.signer.auth_headers(method, path, query=query, body=body)

    async def request(
        self,
        method: HttpMethod,
        path: str,
        *,
        query: JsonDict | None = None,
        body: JsonDict | list[Any] | None = None,
        auth: bool = True,
    ) -> Any:
        ad_hoc = Endpoint("ad_hoc", method.upper(), path, auth, "spot")  # type: ignore[arg-type]
        return await self._execute(ad_hoc, query=query, body=body, path=path)

    async def _execute(
        self,
        endpoint_: Endpoint,
        *,
        query: JsonDict | None = None,
        body: JsonDict | list[Any] | None = None,
        path: str | None = None,
        path_params: JsonDict | None = None,
    ) -> Any:
        request_path = path or endpoint_.path(**drop_none(path_params))
        params = drop_none(query)
        raw_body = json_body(body) if endpoint_.method == "POST" else ""
        headers: JsonDict = {}
        if endpoint_.method == "POST":
            headers["Content-Type"] = "application/json"
        if endpoint_.auth:
            headers.update(
                self._auth_headers(endpoint_.method, request_path, query=params, body=raw_body)
            )

        response = await self.transport.send(
            endpoint_,
            path=request_path,
            query=params,
            body_bytes=raw_body.encode("utf-8") if raw_body else None,
            headers=headers,
        )

        try:
            payload: Any = response.json()
        except ValueError:
            payload = response.text

        if response.status_code >= 400:
            raise MsxHttpError(response.status_code, endpoint_.method, request_path, payload)

        if self.raise_api_errors and isinstance(payload, dict):
            code = payload.get("code")
            if code is not None and str(code) != "0":
                message = str(
                    payload.get("msg") or payload.get("message") or payload.get("error") or ""
                )
                raise MsxApiError(
                    normalize_error_code(code),
                    message,
                    endpoint_.method,
                    request_path,
                    payload,
                )

        return payload

    async def get(self, path: str, *, query: JsonDict | None = None, auth: bool = True) -> Any:
        return await self.request("GET", path, query=query, auth=auth)

    async def post(self, path: str, *, body: JsonDict | list[Any] | None = None) -> Any:
        return await self.request("POST", path, body=body, auth=True)

    async def create_order(self, market: Market, **kwargs: Any) -> Any:
        if market == "spot":
            return await self.create_spot_order(**kwargs)
        if market == "futures":
            return await self.create_futures_order(**kwargs)
        raise ValueError(f"Unsupported MSX market: {market}")

    async def cancel_order(self, market: Market, **kwargs: Any) -> Any:
        if market == "spot":
            return await self.cancel_spot_order(**kwargs)
        if market == "futures":
            return await self.cancel_futures_order(**kwargs)
        raise ValueError(f"Unsupported MSX market: {market}")

    async def get_depth(self, market: Market, **kwargs: Any) -> Any:
        if market == "spot":
            return await self.get_spot_depth(**kwargs)
        if market == "futures":
            return await self.get_futures_orderbook(**kwargs)
        raise ValueError(f"Unsupported MSX market: {market}")

    async def get_klines(self, market: Market, **kwargs: Any) -> Any:
        if market == "spot":
            return await self.get_spot_klines(**kwargs)
        if market == "futures":
            return await self.get_futures_klines(**kwargs)
        raise ValueError(f"Unsupported MSX market: {market}")

    async def get_spot_assets(self, symbol: str | None = None) -> Any:
        return await self._execute(endpoint("spot.assets"), query={"symbol": symbol})

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
        return await self._execute(endpoint("spot.create_order"), body=drop_none(body))

    async def batch_create_spot_orders(self, orders: list[JsonDict]) -> Any:
        return await self._execute(endpoint("spot.batch_create_orders"), body={"orders": orders})

    async def cancel_spot_order(self, *, symbol: str, order_id: str) -> Any:
        return await self._execute(
            endpoint("spot.cancel_order"),
            body={"symbol": symbol, "orderId": order_id},
        )

    async def batch_cancel_spot_orders(self, *, symbol: str, order_ids: list[str]) -> Any:
        return await self._execute(
            endpoint("spot.batch_cancel_orders"),
            body={"symbol": symbol, "orderIds": order_ids},
        )

    async def get_spot_depth(self, *, symbol: str, limit: int | None = None) -> Any:
        return await self._execute(endpoint("spot.depth"), query={"symbol": symbol, "limit": limit})

    async def get_spot_klines(
        self,
        *,
        symbol: str,
        interval: str,
        start_time: int | None = None,
        end_time: int | None = None,
        limit: int | None = None,
    ) -> Any:
        return await self._execute(
            endpoint("spot.klines"),
            query={
                "symbol": symbol,
                "interval": interval,
                "startTime": start_time,
                "endTime": end_time,
                "limit": limit,
            },
        )

    async def get_spot_open_orders(
        self,
        *,
        symbol: str | None = None,
        side: Literal["buy", "sell"] | None = None,
        page: int | None = None,
        size: int | None = None,
    ) -> Any:
        return await self._execute(
            endpoint("spot.open_orders"),
            query={"symbol": symbol, "side": side, "page": page, "size": size},
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
        return await self._execute(
            endpoint("spot.history_orders"),
            query={
                "symbol": symbol,
                "side": side,
                "startTime": start_time,
                "endTime": end_time,
                "page": page,
                "size": size,
            },
        )

    async def get_spot_order_detail(self, *, symbol: str, order_id: str) -> Any:
        return await self._execute(
            endpoint("spot.order_detail"),
            query={"symbol": symbol, "orderId": order_id},
        )

    async def get_spot_price_steps(self, *, symbol: str) -> Any:
        return await self._execute(endpoint("spot.price_steps"), query={"symbol": symbol})

    async def get_spot_ticker(self, *, symbol: str) -> Any:
        return await self._execute(endpoint("spot.ticker"), query={"symbol": symbol})

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
        return await self._execute(
            endpoint("spot.trades"),
            query={
                "symbol": symbol,
                "orderId": order_id,
                "startTime": start_time,
                "endTime": end_time,
                "page": page,
                "size": size,
            },
        )

    async def get_futures_account_config(self, *, symbol: str) -> Any:
        return await self._execute(endpoint("futures.account_config"), query={"symbol": symbol})

    async def set_futures_leverage(
        self,
        *,
        symbol: str,
        leverage: str,
        margin_mode: Literal[1, 2],
    ) -> Any:
        return await self._execute(
            endpoint("futures.set_leverage"),
            body={"symbol": symbol, "leverage": leverage, "marginMode": margin_mode},
        )

    async def set_futures_margin_mode(self, *, symbol: str, margin_mode: Literal[1, 2]) -> Any:
        return await self._execute(
            endpoint("futures.set_margin_mode"),
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
        return await self._execute(
            endpoint("futures.klines"),
            query={
                "symbol": symbol,
                "interval": interval,
                "startTime": start_time,
                "endTime": end_time,
                "limit": limit,
            },
        )

    async def cancel_futures_order(self, *, order_id: int) -> Any:
        return await self._execute(endpoint("futures.cancel_order"), body={"orderId": order_id})

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
        return await self._execute(endpoint("futures.create_order"), body=drop_none(body))

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
        return await self._execute(
            endpoint("futures.entrust_history"),
            body=drop_none(
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
        return await self._execute(
            endpoint("futures.order_history"),
            body=drop_none(
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
        return await self._execute(
            endpoint("futures.open_orders"),
            body=drop_none(
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
        return await self._execute(
            endpoint("futures.orderbook"),
            path_params={"symbol": symbol},
            query={"depth": depth, "with_id": with_id, "step": step},
        )

    async def get_futures_positions(
        self,
        *,
        symbol: str | None = None,
        co_type: int | None = None,
    ) -> Any:
        return await self._execute(
            endpoint("futures.positions"),
            body=drop_none({"symbol": symbol, "coType": co_type}),
        )

    async def get_futures_position_history(
        self,
        *,
        symbol: str | None = None,
        co_type: int | None = None,
        page_index: int | None = None,
        page_size: int | None = None,
    ) -> Any:
        return await self._execute(
            endpoint("futures.position_history"),
            body=drop_none(
                {
                    "symbol": symbol,
                    "coType": co_type,
                    "pageIndex": page_index,
                    "pageSize": page_size,
                }
            ),
        )

    async def get_futures_price_steps(self, *, symbol: str) -> Any:
        return await self._execute(endpoint("futures.price_steps"), path_params={"symbol": symbol})

    async def get_futures_products(self, type: int | None = None) -> Any:
        return await self._execute(endpoint("futures.products"), query={"type": type})

    async def get_futures_ticker(self, *, symbol: str) -> Any:
        return await self._execute(endpoint("futures.ticker"), path_params={"symbol": symbol})

    async def get_legacy_derivatives_products(self) -> Any:
        return await self._execute(endpoint("legacy.products"))

    async def get_legacy_derivatives_ticker_price(self, *, symbol: str) -> Any:
        return await self._execute(endpoint("legacy.ticker_price"), query={"symbol": symbol})

    async def get_legacy_derivatives_depth(
        self,
        *,
        symbol: str,
        limit: int | None = None,
    ) -> Any:
        return await self._execute(
            endpoint("legacy.depth"),
            query={"symbol": symbol, "limit": limit},
        )


__all__ = [
    "MsxApiError",
    "MsxAuthError",
    "MsxHttpError",
    "MsxRestClient",
    "MsxRestError",
]
