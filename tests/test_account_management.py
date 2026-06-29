import pytest
from cryptography.fernet import Fernet
from pydantic import ValidationError
from sqlalchemy import delete

from app.core.config import settings
from app.domain.accounts import AccountCredentialPayload, ExchangeAccountCreateRequest
from app.services.account_credentials import AccountCredentialService
from app.services.exchange_account_service import ExchangeAccountService
from app.storage.db import SessionLocal, create_db_and_tables
from app.storage.models import AccountBalanceSnapshotRecord, ExchangeAccountRecord


def test_account_create_request_only_allows_msx() -> None:
    with pytest.raises(ValidationError):
        ExchangeAccountCreateRequest(
            name="bad",
            exchange="GATE",
            credentials=AccountCredentialPayload(api_key="key", api_secret="secret"),
        )


def test_account_credentials_encrypt_decrypt_and_mask() -> None:
    settings.account_credentials_fernet_key = Fernet.generate_key().decode()
    service = AccountCredentialService()

    encrypted, fingerprint, summary = service.encrypt(
        AccountCredentialPayload(api_key="abcdef123456", api_secret="secret123456")
    )
    decrypted = service.decrypt(encrypted)

    assert fingerprint
    assert decrypted == {"api_key": "abcdef123456", "api_secret": "secret123456"}
    assert summary["api_key"] == "abcd****3456"
    assert summary["api_secret"] == "secr****3456"


def test_extract_msx_equity_from_assets_payload() -> None:
    payloads = {
        "assets": {
            "code": 0,
            "data": [
                {"asset": "USDT", "available": "10.5", "equity": "12.25"},
                {"asset": "BTC", "valueUsdt": "100.75"},
            ],
        }
    }

    balance, equity = ExchangeAccountService._extract_msx_equity(payloads)

    assert balance == 10.5
    assert equity == 113.0


def test_snapshot_account_balance_records_history_and_updates_account() -> None:
    create_db_and_tables()
    with SessionLocal() as session:
        session.execute(delete(AccountBalanceSnapshotRecord))
        session.execute(delete(ExchangeAccountRecord))
        account = ExchangeAccountRecord(
            name="snapshot account",
            account_type="cex",
            exchange="MSX",
            status="unverified",
            enabled=True,
            credentials_encrypted="test",
            credential_fingerprint="fp",
            credential_summary_json="{}",
        )
        session.add(account)
        session.commit()
        account_id = account.id

    class SnapshotTester:
        async def test(self, record: ExchangeAccountRecord):
            return (
                "healthy",
                "ok",
                [],
                {
                    "assets": {
                        "data": [
                            {"asset": "USDT", "available": "15", "equity": "20"},
                            {"asset": "BTC", "valueUsdt": "30"},
                        ]
                    }
                },
            )

    service = ExchangeAccountService(tester=SnapshotTester())  # type: ignore[arg-type]
    snapshot = asyncio_run(service.snapshot_account_balance(account_id))

    assert snapshot.balance_usdt == 15
    assert snapshot.equity_usdt == 50
    assert snapshot.status == "healthy"
    with SessionLocal() as session:
        account = session.get(ExchangeAccountRecord, account_id)
        assert account is not None
        assert account.latest_balance_usdt == 15
        assert account.latest_equity_usdt == 50


def asyncio_run(coro):
    import asyncio

    return asyncio.run(coro)
