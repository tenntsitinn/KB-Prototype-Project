from pydantic import BaseModel


class MetricsResponse(BaseModel):
    total_visits: int
    unique_users: int
    knowledge_unit_count: int
    total_tokens: int
    avg_response_ms: int


class RankingItem(BaseModel):
    text: str
    count: int


class RankingsResponse(BaseModel):
    items: list[RankingItem]


class TokenTrendItem(BaseModel):
    date: str
    total_tokens: int
    avg_response_ms: int
    request_count: int


class TokenTrendsResponse(BaseModel):
    items: list[TokenTrendItem]