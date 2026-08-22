from datetime import datetime
from pydantic import BaseModel, Field


class TagCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    sort_order: int = 0


class TagUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=128)
    sort_order: int | None = None


class TagOut(BaseModel):
    id: str
    name: str
    sort_order: int
    created_at: datetime
