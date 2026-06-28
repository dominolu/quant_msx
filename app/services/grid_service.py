from app.domain.grid import GridListView, GridSummaryView


class GridService:
    """Grid strategy application service skeleton."""

    async def list_grids(self) -> GridListView:
        return GridListView(summary=GridSummaryView(), items=[])
