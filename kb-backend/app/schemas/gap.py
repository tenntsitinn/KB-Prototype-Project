from datetime import datetime
from pydantic import BaseModel


class KnowledgeGapOut(BaseModel):
    id: str
    question_pattern: str
    sample_questions: list[str]
    ask_count: int
    last_asked_at: datetime | None
    status: str
    resolved_unit_id: str
    created_at: datetime


class KnowledgeGapListResponse(BaseModel):
    items: list[KnowledgeGapOut]
    total: int


class ResolveGapRequest(BaseModel):
    unit_id: str = ""