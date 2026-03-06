from typing import Optional
from pydantic import BaseModel


class WatchlistAdd(BaseModel):
    property_id: int
    notes: Optional[str] = None


class WatchlistUpdate(BaseModel):
    notes: str
