from __future__ import annotations

import hashlib
import json

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings
from app.domain.accounts import AccountCredentialPayload

SENSITIVE_FIELDS = {"api_key", "api_secret"}


class AccountCredentialError(ValueError):
    pass


class AccountCredentialService:
    def _fernet(self) -> Fernet:
        key = settings.account_credentials_fernet_key.strip()
        if not key:
            raise AccountCredentialError("ACCOUNT_CREDENTIALS_FERNET_KEY is required")
        try:
            return Fernet(key.encode("utf-8"))
        except ValueError as exc:
            raise AccountCredentialError("ACCOUNT_CREDENTIALS_FERNET_KEY is invalid") from exc

    def encrypt(self, payload: AccountCredentialPayload) -> tuple[str, str, dict[str, str]]:
        raw = self.clean_payload(payload)
        if not raw:
            raise AccountCredentialError("credentials are required")
        encoded = json.dumps(raw, sort_keys=True, separators=(",", ":")).encode("utf-8")
        encrypted = self._fernet().encrypt(encoded).decode("utf-8")
        fingerprint = hashlib.sha256(encoded).hexdigest()
        return encrypted, fingerprint, self.summarize(raw, fingerprint)

    def decrypt(self, encrypted: str) -> dict[str, str]:
        try:
            raw = self._fernet().decrypt(encrypted.encode("utf-8"))
        except InvalidToken as exc:
            raise AccountCredentialError("stored credentials cannot be decrypted") from exc
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict):
            raise AccountCredentialError("stored credentials have invalid format")
        return {str(key): str(value) for key, value in payload.items() if value is not None}

    def summarize(self, payload: dict[str, str], fingerprint: str) -> dict[str, str]:
        summary: dict[str, str] = {"fingerprint": fingerprint[:16]}
        for key, value in payload.items():
            summary[key] = self._mask(value) if key in SENSITIVE_FIELDS else value
        return summary

    def clean_payload(self, payload: AccountCredentialPayload) -> dict[str, str]:
        data = payload.model_dump()
        cleaned: dict[str, str] = {}
        for key, value in data.items():
            if value is None:
                continue
            stripped = str(value).strip()
            if stripped:
                cleaned[key] = stripped
        return cleaned

    @staticmethod
    def _mask(value: str) -> str:
        if len(value) <= 8:
            return "****"
        return f"{value[:4]}****{value[-4:]}"
