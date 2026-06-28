import pytest
from cryptography.fernet import Fernet
from pydantic import ValidationError

from app.core.config import settings
from app.domain.accounts import AccountCredentialPayload, ExchangeAccountCreateRequest
from app.services.account_credentials import AccountCredentialService
from app.services.exchange_account_service import ExchangeAccountService


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
