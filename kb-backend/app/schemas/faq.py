from datetime import datetime
from pydantic import BaseModel


class FAQRecommendationOut(BaseModel):
    id: str
    question: str
    answer: str
    related_unit_id: str
    source_type: str
    status: str
    hit_count: int
    created_at: datetime


class FAQRecommendationListResponse(BaseModel):
    items: list[FAQRecommendationOut]
    total: int


class FAQReviewRequest(BaseModel):
    action: str = ""  # approve | reject
    edited_answer: str = ""
    question: str = ""
    answer: str = ""


class FAQPublishedOut(BaseModel):
    id: str
    question: str
    answer: str
    source_type: str
    hit_count: int
    reviewer_id: str
    reviewed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class FAQPublishedListResponse(BaseModel):
    items: list[FAQPublishedOut]
    total: int