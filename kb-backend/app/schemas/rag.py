from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, description="用户提问")
    session_id: str | None = Field(default=None, description="会话ID，用于多轮对话")
    stream: bool = Field(default=False, description="是否流式返回")
    top_k: int = Field(default=10, ge=1, le=50, description="期望返回的检索结果数量")
    chapter_id: str | None = Field(default=None, description="限定检索范围的章节ID（递归含子孙）")


class SourceInfo(BaseModel):
    unit_id: str
    unit_code: str
    title: str = ""
    chunk_index: int
    chunk_text: str
    score: float
    source: str  # embedding | hyde | keyword


class AskResponse(BaseModel):
    answer: str
    sources: list[SourceInfo]
    session_id: str
    response_time_ms: int


class SessionItem(BaseModel):
    session_id: str
    first_question: str
    message_count: int
    created_at: str
    updated_at: str


class SessionMessage(BaseModel):
    role: str  # user | assistant
    content: str
    sources: list[SourceInfo] = []
    created_at: str