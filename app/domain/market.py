from pydantic import BaseModel


class BestBidAsk(BaseModel):
    market: str
    symbol: str
    bid_price: str
    bid_qty: str
    ask_price: str
    ask_qty: str
    updated_at: str
