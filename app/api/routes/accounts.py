from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Response

from app.domain.accounts import ExchangeAccountCreateRequest, ExchangeAccountUpdateRequest
from app.services.account_credentials import AccountCredentialError
from app.services.exchange_account_service import (
    ExchangeAccountError,
    ExchangeAccountNotFoundError,
    ExchangeAccountService,
)

router = APIRouter(prefix="/api/accounts", tags=["accounts"])
service = ExchangeAccountService()


@router.get("/summary")
async def account_summary() -> dict[str, object]:
    return service.get_summary().model_dump()


@router.get("")
async def list_accounts(
    account_type: str | None = Query(default=None),
    exchange: str | None = Query(default=None),
    status: str | None = Query(default=None),
) -> dict[str, object]:
    return service.list_accounts(
        account_type=account_type,
        exchange=exchange,
        status=status,
    ).model_dump()


@router.post("")
async def create_account(request: ExchangeAccountCreateRequest) -> dict[str, object]:
    try:
        return service.create_account(request).model_dump()
    except (AccountCredentialError, ExchangeAccountError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{account_id}")
async def get_account(account_id: int) -> dict[str, object]:
    try:
        return service.get_account(account_id).model_dump()
    except ExchangeAccountNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/{account_id}")
async def update_account(
    account_id: int,
    request: ExchangeAccountUpdateRequest,
) -> dict[str, object]:
    try:
        return service.update_account(account_id, request).model_dump()
    except ExchangeAccountNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (AccountCredentialError, ExchangeAccountError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{account_id}/test")
async def test_account(account_id: int) -> dict[str, object]:
    try:
        return (await service.test_connection(account_id)).model_dump()
    except ExchangeAccountNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AccountCredentialError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{account_id}/disable")
async def disable_account(account_id: int) -> dict[str, object]:
    try:
        return service.disable_account(account_id).model_dump()
    except ExchangeAccountNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{account_id}/enable")
async def enable_account(account_id: int) -> dict[str, object]:
    try:
        return service.enable_account(account_id).model_dump()
    except ExchangeAccountNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{account_id}", status_code=204)
async def delete_account(account_id: int) -> Response:
    try:
        service.delete_account(account_id)
    except ExchangeAccountNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(status_code=204)
