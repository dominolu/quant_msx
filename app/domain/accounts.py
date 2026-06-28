from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

AccountType = Literal["cex"]
AccountStatus = Literal["unverified", "healthy", "error", "disabled"]


class AccountCredentialPayload(BaseModel):
    api_key: str | None = None
    api_secret: str | None = None


class ExchangeAccountCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    account_type: AccountType = "cex"
    exchange: str = "MSX"
    credentials: AccountCredentialPayload
    permissions: dict[str, object] = Field(default_factory=dict)
    connection_config: dict[str, object] = Field(default_factory=dict)
    enabled: bool = True
    notes: str = ""

    @field_validator("exchange")
    @classmethod
    def normalize_exchange(cls, value: str) -> str:
        normalized = value.strip().upper()
        if normalized != "MSX":
            raise ValueError("only MSX accounts are supported")
        return normalized


class ExchangeAccountUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    exchange: str | None = Field(default=None, min_length=1, max_length=64)
    credentials: AccountCredentialPayload | None = None
    permissions: dict[str, object] | None = None
    connection_config: dict[str, object] | None = None
    enabled: bool | None = None
    notes: str | None = None

    @field_validator("exchange")
    @classmethod
    def normalize_exchange(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().upper()
        if normalized != "MSX":
            raise ValueError("only MSX accounts are supported")
        return normalized


class CredentialSummaryView(BaseModel):
    fields: dict[str, str] = Field(default_factory=dict)
    fingerprint: str


class ExchangeAccountView(BaseModel):
    id: int
    name: str
    account_type: str
    exchange: str
    status: AccountStatus
    enabled: bool
    credential_summary: CredentialSummaryView
    permissions: dict[str, object]
    connection_config: dict[str, object]
    latest_balance_usdt: str
    latest_equity_usdt: str
    equity_curve_points: list[float]
    last_checked_at: datetime | None
    last_error: str
    notes: str
    created_at: datetime
    updated_at: datetime


class ExchangeAccountListView(BaseModel):
    items: list[ExchangeAccountView] = Field(default_factory=list)


class ExchangeAccountSummaryView(BaseModel):
    total_balance_usdt: str
    enabled_account_count: int
    healthy_account_count: int
    error_account_count: int
    disabled_account_count: int
    last_balance_synced_at: datetime | None


class AccountConnectionCheckItemView(BaseModel):
    name: str
    status: str
    message: str


class AccountConnectionTestView(BaseModel):
    account: ExchangeAccountView
    status: AccountStatus
    message: str
    checks: list[AccountConnectionCheckItemView]
