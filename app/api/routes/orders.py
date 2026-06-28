from fastapi import APIRouter, HTTPException, Query

from app.domain.orders import OrderCancelRequest, OrderSubmitRequest
from app.services.order_service import OrderService

router = APIRouter(prefix="/api", tags=["orders"])
service = OrderService()


@router.get("/orders")
async def list_orders(
    source: str | None = Query(default=None),
    source_id: int | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int | None = Query(default=200),
) -> dict[str, object]:
    return service.list_orders(
        source=source,
        source_id=source_id,
        status=status,
        limit=limit,
    ).model_dump()


@router.post("/orders")
async def submit_order(request: OrderSubmitRequest) -> dict[str, object]:
    try:
        return (await service.place_order(request)).model_dump()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/orders/cancel")
async def cancel_order(request: OrderCancelRequest) -> dict[str, object]:
    try:
        return (await service.cancel_order(request)).model_dump()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

