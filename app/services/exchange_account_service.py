from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import delete, select

from app.broker.msx_rest import MsxRestClient
from app.domain.accounts import (
    AccountCredentialPayload,
    AccountConnectionCheckItemView,
    AccountConnectionTestView,
    CredentialSummaryView,
    ExchangeAccountCreateRequest,
    ExchangeAccountListView,
    ExchangeAccountSummaryView,
    ExchangeAccountUpdateRequest,
    ExchangeAccountView,
)
from app.services.account_credentials import AccountCredentialError, AccountCredentialService
from app.storage.db import SessionLocal
from app.storage.models import AccountBalanceSnapshotRecord, ExchangeAccountRecord


class ExchangeAccountError(ValueError):
    pass


class ExchangeAccountNotFoundError(ExchangeAccountError):
    pass


class ExchangeConnectionTester:
    def __init__(self, credential_service: AccountCredentialService | None = None) -> None:
        self.credential_service = credential_service or AccountCredentialService()

    async def test(
        self,
        record: ExchangeAccountRecord,
    ) -> tuple[str, str, list[AccountConnectionCheckItemView], dict[str, Any]]:
        credentials = self.credential_service.decrypt(record.credentials_encrypted)
        api_key = credentials.get("api_key", "")
        api_secret = credentials.get("api_secret", "")
        checks: list[AccountConnectionCheckItemView] = []
        payloads: dict[str, Any] = {}

        async with MsxRestClient(api_key=api_key, secret_key=api_secret) as client:
            for name, call in (
                ("assets", client.get_spot_assets),
                ("spot_open_orders", client.get_spot_open_orders),
                ("futures_positions", client.get_futures_positions),
                ("futures_open_orders", client.get_futures_open_orders),
            ):
                try:
                    payload = await call()
                except Exception as exc:
                    message = f"{type(exc).__name__}: {exc}"
                    checks.append(
                        AccountConnectionCheckItemView(
                            name=name,
                            status="error",
                            message=message,
                        )
                    )
                    return "error", f"MSX {name} check failed: {message}", checks, payloads
                payloads[name] = payload
                checks.append(
                    AccountConnectionCheckItemView(name=name, status="ok", message="ok")
                )

        checks.append(
            AccountConnectionCheckItemView(
                name="time_sync",
                status="ok",
                message="signed requests accepted by MSX",
            )
        )
        return "healthy", "MSX connection verified", checks, payloads


class ExchangeAccountService:
    def __init__(
        self,
        credential_service: AccountCredentialService | None = None,
        tester: ExchangeConnectionTester | None = None,
    ) -> None:
        self.credential_service = credential_service or AccountCredentialService()
        self.tester = tester or ExchangeConnectionTester(self.credential_service)

    def list_accounts(
        self,
        account_type: str | None = None,
        exchange: str | None = None,
        status: str | None = None,
    ) -> ExchangeAccountListView:
        with SessionLocal() as session:
            statement = select(ExchangeAccountRecord).order_by(
                ExchangeAccountRecord.updated_at.desc()
            )
            if account_type:
                statement = statement.where(
                    ExchangeAccountRecord.account_type == account_type.lower()
                )
            if exchange:
                statement = statement.where(ExchangeAccountRecord.exchange == exchange.upper())
            if status:
                statement = statement.where(ExchangeAccountRecord.status == status.lower())
            records = session.execute(statement).scalars().all()
            return ExchangeAccountListView(items=[self._to_view(record) for record in records])

    def get_summary(self) -> ExchangeAccountSummaryView:
        with SessionLocal() as session:
            records = session.execute(select(ExchangeAccountRecord)).scalars().all()
            enabled = [
                record for record in records if record.enabled and record.status != "disabled"
            ]
            last_synced = max(
                (
                    record.last_checked_at
                    for record in records
                    if record.last_checked_at is not None
                ),
                default=None,
            )
            return ExchangeAccountSummaryView(
                total_balance_usdt=self._format_number(
                    sum(record.latest_equity_usdt for record in enabled)
                ),
                enabled_account_count=len(enabled),
                healthy_account_count=sum(1 for record in records if record.status == "healthy"),
                error_account_count=sum(1 for record in records if record.status == "error"),
                disabled_account_count=sum(
                    1 for record in records if (not record.enabled or record.status == "disabled")
                ),
                last_balance_synced_at=last_synced,
            )

    def get_account(self, account_id: int) -> ExchangeAccountView:
        with SessionLocal() as session:
            record = session.get(ExchangeAccountRecord, account_id)
            if record is None:
                raise ExchangeAccountNotFoundError("account not found")
            return self._to_view(record)

    def create_account(self, request: ExchangeAccountCreateRequest) -> ExchangeAccountView:
        self._validate_msx(request.account_type, request.exchange)
        encrypted, fingerprint, credential_summary = self._encrypt_credentials(request.credentials)
        now = datetime.utcnow()
        record = ExchangeAccountRecord(
            name=request.name.strip(),
            account_type=request.account_type,
            exchange=request.exchange,
            status="unverified" if request.enabled else "disabled",
            enabled=request.enabled,
            credentials_encrypted=encrypted,
            credential_fingerprint=fingerprint,
            credential_summary_json=json.dumps(credential_summary, sort_keys=True),
            permissions_json=json.dumps(request.permissions, sort_keys=True),
            connection_config_json=json.dumps(request.connection_config, sort_keys=True),
            latest_balance_usdt=0.0,
            latest_equity_usdt=0.0,
            equity_curve_points_json="[]",
            notes=request.notes,
            created_at=now,
            updated_at=now,
        )
        with SessionLocal() as session:
            session.add(record)
            session.commit()
            session.refresh(record)
            return self._to_view(record)

    def update_account(
        self,
        account_id: int,
        request: ExchangeAccountUpdateRequest,
    ) -> ExchangeAccountView:
        with SessionLocal() as session:
            record = session.get(ExchangeAccountRecord, account_id)
            if record is None:
                raise ExchangeAccountNotFoundError("account not found")
            if request.name is not None:
                record.name = request.name.strip()
            if request.exchange is not None:
                self._validate_msx(record.account_type, request.exchange)
                record.exchange = request.exchange
            if request.credentials is not None:
                encrypted, fingerprint, credential_summary = self._encrypt_credentials(
                    request.credentials
                )
                record.credentials_encrypted = encrypted
                record.credential_fingerprint = fingerprint
                record.credential_summary_json = json.dumps(credential_summary, sort_keys=True)
                record.status = "unverified" if record.enabled else "disabled"
                record.last_error = ""
                record.last_checked_at = None
            if request.permissions is not None:
                record.permissions_json = json.dumps(request.permissions, sort_keys=True)
            if request.connection_config is not None:
                record.connection_config_json = json.dumps(
                    request.connection_config,
                    sort_keys=True,
                )
            if request.enabled is not None:
                record.enabled = request.enabled
                if not request.enabled:
                    record.status = "disabled"
                elif record.status == "disabled":
                    record.status = "unverified"
            if request.notes is not None:
                record.notes = request.notes
            record.updated_at = datetime.utcnow()
            session.commit()
            session.refresh(record)
            return self._to_view(record)

    def enable_account(self, account_id: int) -> ExchangeAccountView:
        return self.update_account(account_id, ExchangeAccountUpdateRequest(enabled=True))

    def disable_account(self, account_id: int) -> ExchangeAccountView:
        return self.update_account(account_id, ExchangeAccountUpdateRequest(enabled=False))

    def delete_account(self, account_id: int) -> None:
        with SessionLocal() as session:
            record = session.get(ExchangeAccountRecord, account_id)
            if record is None:
                raise ExchangeAccountNotFoundError("account not found")
            session.execute(
                delete(ExchangeAccountRecord).where(ExchangeAccountRecord.id == account_id)
            )
            session.commit()

    async def test_connection(self, account_id: int) -> AccountConnectionTestView:
        with SessionLocal() as session:
            record = session.get(ExchangeAccountRecord, account_id)
            if record is None:
                raise ExchangeAccountNotFoundError("account not found")
            detached_record = record

        status, message, checks, payloads = await self.tester.test(detached_record)

        with SessionLocal() as session:
            record = session.get(ExchangeAccountRecord, account_id)
            if record is None:
                raise ExchangeAccountNotFoundError("account not found")
            record.status = status
            record.last_error = message if status != "healthy" else ""
            record.last_checked_at = datetime.utcnow()
            if status == "healthy":
                balance, equity = self._extract_msx_equity(payloads)
                record.latest_balance_usdt = balance
                record.latest_equity_usdt = equity
                points = self._load_json(record.equity_curve_points_json, [])
                if not isinstance(points, list):
                    points = []
                points = [float(point) for point in points if isinstance(point, int | float)]
                if equity != 0:
                    points.append(equity)
                    points = points[-120:]
                record.equity_curve_points_json = json.dumps(points)
            record.updated_at = datetime.utcnow()
            session.commit()
            session.refresh(record)
            return AccountConnectionTestView(
                account=self._to_view(record),
                status=status,  # type: ignore[arg-type]
                message=message,
                checks=checks,
            )

    def list_enabled_account_ids(self) -> list[int]:
        with SessionLocal() as session:
            rows = session.scalars(
                select(ExchangeAccountRecord.id).where(
                    ExchangeAccountRecord.enabled.is_(True),
                    ExchangeAccountRecord.status != "disabled",
                )
            ).all()
            return [int(row) for row in rows]

    async def snapshot_enabled_accounts(self) -> dict[str, int]:
        attempted = succeeded = failed = 0
        for account_id in self.list_enabled_account_ids():
            attempted += 1
            try:
                await self.snapshot_account_balance(account_id)
            except Exception:
                failed += 1
            else:
                succeeded += 1
        return {"attempted": attempted, "succeeded": succeeded, "failed": failed}

    async def snapshot_account_balance(self, account_id: int) -> AccountBalanceSnapshotRecord:
        with SessionLocal() as session:
            record = session.get(ExchangeAccountRecord, account_id)
            if record is None:
                raise ExchangeAccountNotFoundError("account not found")
            if not record.enabled or record.status == "disabled":
                raise ExchangeAccountError("account is disabled")
            detached_record = record

        try:
            status, message, _checks, payloads = await self.tester.test(detached_record)
            balance, equity = self._extract_msx_equity(payloads) if status == "healthy" else (0.0, 0.0)
        except Exception as exc:
            status = "error"
            message = f"{type(exc).__name__}: {exc}"
            payloads = {}
            balance = equity = 0.0

        now = datetime.utcnow()
        with SessionLocal() as session:
            record = session.get(ExchangeAccountRecord, account_id)
            if record is None:
                raise ExchangeAccountNotFoundError("account not found")
            record.status = status
            record.last_error = message if status != "healthy" else ""
            record.last_checked_at = now
            if status == "healthy":
                record.latest_balance_usdt = balance
                record.latest_equity_usdt = equity
                points = self._load_json(record.equity_curve_points_json, [])
                if not isinstance(points, list):
                    points = []
                points = [float(point) for point in points if isinstance(point, int | float)]
                if equity != 0:
                    points.append(equity)
                    points = points[-120:]
                record.equity_curve_points_json = json.dumps(points)
            record.updated_at = now
            snapshot = AccountBalanceSnapshotRecord(
                account_id=account_id,
                balance_usdt=balance,
                equity_usdt=equity,
                status=status,
                error_message=message if status != "healthy" else "",
                raw_payload_json=json.dumps(payloads, sort_keys=True, default=str),
                created_at=now,
            )
            session.add(snapshot)
            session.commit()
            session.refresh(snapshot)
            session.expunge(snapshot)
            return snapshot

    def _to_view(self, record: ExchangeAccountRecord) -> ExchangeAccountView:
        credential_summary = self._load_json(record.credential_summary_json, {})
        permissions = self._load_json(record.permissions_json, {})
        connection_config = self._load_json(record.connection_config_json, {})
        equity_curve_points = self._load_json(record.equity_curve_points_json, [])
        if not isinstance(equity_curve_points, list):
            equity_curve_points = []
        return ExchangeAccountView(
            id=record.id,
            name=record.name,
            account_type=record.account_type,
            exchange=record.exchange,
            status=record.status,  # type: ignore[arg-type]
            enabled=record.enabled,
            credential_summary=CredentialSummaryView(
                fields={
                    str(key): str(value)
                    for key, value in self._as_dict(credential_summary).items()
                    if key != "fingerprint"
                },
                fingerprint=str(self._as_dict(credential_summary).get("fingerprint") or "")
                or record.credential_fingerprint[:16],
            ),
            permissions=self._as_dict(permissions),
            connection_config=self._as_dict(connection_config),
            latest_balance_usdt=self._format_number(record.latest_balance_usdt),
            latest_equity_usdt=self._format_number(record.latest_equity_usdt),
            equity_curve_points=[
                float(point) for point in equity_curve_points if isinstance(point, int | float)
            ],
            last_checked_at=record.last_checked_at,
            last_error=record.last_error,
            notes=record.notes,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    def _encrypt_credentials(
        self,
        payload: AccountCredentialPayload,
    ) -> tuple[str, str, dict[str, str]]:
        raw = self.credential_service.clean_payload(payload)
        self._validate_complete_credentials(raw)
        normalized = AccountCredentialPayload(**raw)
        return self.credential_service.encrypt(normalized)

    @staticmethod
    def _validate_msx(account_type: str, exchange: str) -> None:
        if account_type != "cex" or exchange.upper() != "MSX":
            raise ExchangeAccountError("only MSX cex accounts are supported")

    @staticmethod
    def _validate_complete_credentials(raw: dict[str, str]) -> None:
        required = {"api_key", "api_secret"}
        missing = sorted(field for field in required if not raw.get(field))
        if missing:
            raise AccountCredentialError(f"incomplete credentials: missing {', '.join(missing)}")

    @staticmethod
    def _load_json(raw: str, default: object) -> object:
        try:
            return json.loads(raw or "")
        except json.JSONDecodeError:
            return default

    @classmethod
    def _extract_msx_equity(cls, payloads: dict[str, Any]) -> tuple[float, float]:
        assets_payload = payloads.get("assets")
        items = cls._extract_items(assets_payload)
        usdt_balance = 0.0
        total_equity = 0.0
        for item in items:
            asset = str(
                item.get("asset")
                or item.get("currency")
                or item.get("coin")
                or item.get("symbol")
                or ""
            ).upper()
            available = cls._first_float(
                item,
                "available",
                "availableBalance",
                "available_balance",
                "free",
                "balance",
            )
            equity = cls._first_float(
                item,
                "equityValueUsdt",
                "equity_value_usdt",
                "equity",
                "total",
                "balance",
            )
            if asset in {"USDT", "USD"}:
                usdt_balance += available
                total_equity += equity or available
            elif "valueUsdt" in item or "value_usdt" in item:
                total_equity += cls._first_float(item, "valueUsdt", "value_usdt")
        return usdt_balance, total_equity or usdt_balance

    @classmethod
    def _extract_items(cls, payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if not isinstance(payload, dict):
            return []
        for key in ("data", "items", "list", "assets", "balances"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
            if isinstance(value, dict):
                nested = cls._extract_items(value)
                if nested:
                    return nested
        return []

    @staticmethod
    def _first_float(item: dict[str, Any], *keys: str) -> float:
        for key in keys:
            if key in item:
                return ExchangeAccountService._to_float(item.get(key))
        return 0.0

    @staticmethod
    def _to_float(value: object) -> float:
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _format_number(value: float) -> str:
        if value == 0:
            return "0"
        return f"{value:.8f}".rstrip("0").rstrip(".")

    @staticmethod
    def _as_dict(value: object) -> dict[str, object]:
        return value if isinstance(value, dict) else {}
