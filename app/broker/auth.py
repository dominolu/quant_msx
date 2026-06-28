from __future__ import annotations

import base64
import hashlib
import hmac
import time
from dataclasses import dataclass

from app.broker.common import JsonDict, build_query_string


@dataclass(slots=True)
class MsxCredentials:
    api_key: str = ""
    secret_key: str = ""

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.secret_key)


class MsxSigner:
    def __init__(self, credentials: MsxCredentials) -> None:
        self.credentials = credentials

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
        query_string = build_query_string(query)
        payload = f"{ts}{method.upper()}{request_path}{query_string}{body}"
        digest = hmac.new(
            self.credentials.secret_key.encode(),
            payload.encode(),
            hashlib.sha256,
        ).digest()
        return ts, base64.b64encode(digest).decode()

    def auth_headers(
        self,
        method: str,
        request_path: str,
        *,
        query: JsonDict | None = None,
        body: str = "",
    ) -> JsonDict:
        timestamp, signature = self.sign(method, request_path, query=query, body=body)
        return {
            "ACCESS-KEY": self.credentials.api_key,
            "ACCESS-SIGN": signature,
            "ACCESS-TIMESTAMP": timestamp,
        }
