from dataclasses import dataclass


@dataclass(slots=True)
class RuntimeState:
    started: bool = False
    market_ws_status: str = "unknown"
    private_ws_status: str = "unknown"


runtime_state = RuntimeState()
