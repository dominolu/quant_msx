class OrderService:
    """Order command boundary.

    Real trading code must pass through this service so risk checks and audit logs are central.
    """

    async def place_order(self) -> None:
        raise NotImplementedError
