from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import urlencode

JsonDict = dict[str, Any]
HttpMethod = Literal["GET", "POST"]
Market = Literal["spot", "futures"]


class BrokerError(Exception):
    """Base class for broker-layer errors."""


class MsxRestError(BrokerError):
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
    code: int | str
    message: str
    method: str
    path: str
    payload: JsonDict

    def __str__(self) -> str:
        return f"MSX API code={self.code} for {self.method} {self.path}: {self.message}"


class MsxAuthError(MsxRestError):
    """Raised when an authenticated endpoint is used without credentials."""


class MsxRateLimitError(MsxRestError):
    """Raised when local or remote rate limiting rejects a request."""


def drop_none(params: JsonDict | None) -> JsonDict:
    return {key: value for key, value in (params or {}).items() if value is not None}


def query_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def build_query_string(query: JsonDict | None) -> str:
    params = drop_none(query)
    if not params:
        return ""
    sorted_items = [(key, query_value(params[key])) for key in sorted(params)]
    return "?" + urlencode(sorted_items)


def json_body(data: JsonDict | list[Any] | None) -> str:
    if data is None:
        return ""
    return json.dumps(data, separators=(",", ":"), ensure_ascii=False)


def normalize_error_code(code: Any) -> int | str:
    try:
        return int(code)
    except (TypeError, ValueError):
        return str(code)
