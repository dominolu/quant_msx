from fastapi import APIRouter, HTTPException, Query

from app.core.config import settings
from app.domain.grid import GridCreateRequest, GridFillRequest, GridReconfigureRequest
from app.services.grid_service import GridService

router = APIRouter(prefix="/api", tags=["grids"])
service = GridService()


@router.get("/contract-grids")
async def list_contract_grids(status: str | None = Query(default=None)) -> dict[str, object]:
    return (await service.list_grids(status=status)).model_dump()


@router.post("/contract-grids")
async def create_contract_grid(request: GridCreateRequest) -> dict[str, object]:
    try:
        return (await service.create_grid(request)).model_dump()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/contract-grids/{grid_id}")
async def get_contract_grid(grid_id: int) -> dict[str, object]:
    try:
        return service.get_detail(grid_id).model_dump()
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/contract-grids/{grid_id}/start")
async def start_contract_grid(grid_id: int) -> dict[str, object]:
    try:
        return (await service.start_grid(grid_id)).model_dump()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/contract-grids/{grid_id}/params")
async def reconfigure_contract_grid(
    grid_id: int,
    request: GridReconfigureRequest,
) -> dict[str, object]:
    try:
        return (await service.reconfigure_grid(grid_id, request)).model_dump()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/contract-grids/sync")
async def sync_contract_grids() -> dict[str, object]:
    try:
        return (await service.sync_grid_from_rest()).model_dump()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/contract-grids/{grid_id}/sync")
async def sync_contract_grid(grid_id: int) -> dict[str, object]:
    try:
        return (await service.sync_grid_from_rest(grid_id)).model_dump()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/contract-grids/{grid_id}/pause")
async def pause_contract_grid(grid_id: int) -> dict[str, object]:
    try:
        return (await service.pause_grid(grid_id)).model_dump()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/contract-grids/{grid_id}/resume")
async def resume_contract_grid(grid_id: int) -> dict[str, object]:
    try:
        return (await service.resume_grid(grid_id)).model_dump()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/contract-grids/{grid_id}/stop")
async def stop_contract_grid(grid_id: int) -> dict[str, object]:
    try:
        return (await service.stop_grid(grid_id)).model_dump()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/contract-grids/{grid_id}")
async def delete_contract_grid(grid_id: int) -> dict[str, object]:
    try:
        return service.delete_grid(grid_id).model_dump()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/contract-grids/{grid_id}/orders")
async def list_contract_grid_orders(grid_id: int) -> dict[str, object]:
    try:
        service.ensure_grid_exists(grid_id)
        return {"items": [item.model_dump() for item in service.list_orders(grid_id)]}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/contract-grids/{grid_id}/orders/{order_id}/fill")
async def fill_contract_grid_order(
    grid_id: int,
    order_id: int,
    request: GridFillRequest,
) -> dict[str, object]:
    if settings.live_trading_enabled and not settings.grid_demo_mode:
        raise HTTPException(status_code=403, detail="manual fill is only available in demo mode")
    try:
        return (await service.handle_order_filled(grid_id, order_id, request)).model_dump()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/contract-grids/{grid_id}/fills")
async def list_contract_grid_fills(grid_id: int) -> dict[str, object]:
    try:
        service.ensure_grid_exists(grid_id)
        return {"items": [item.model_dump() for item in service.list_fills(grid_id)]}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/contract-grids/{grid_id}/events")
async def list_contract_grid_events(grid_id: int) -> dict[str, object]:
    try:
        service.ensure_grid_exists(grid_id)
        return {"items": [item.model_dump() for item in service.list_events(grid_id)]}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
