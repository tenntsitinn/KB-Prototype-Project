from datetime import datetime
from pydantic import BaseModel, Field


# --- 出题 ---

class NextQuestionRequest(BaseModel):
    category: str = ""
    source_unit_id: str = ""
    source_unit_ids: list[str] = Field(default_factory=list)
    asked_question_ids: list[str] = Field(default_factory=list)


class NextQuestionResponse(BaseModel):
    question_id: str
    question: str
    from_bank: bool
    source_unit_id: str = ""
    reference_answer: str = ""


# --- 判分 ---

class AnswerRequest(BaseModel):
    question_id: str
    answer_text: str = ""


class AnswerResponse(BaseModel):
    question_id: str
    question: str
    score: int
    feedback: str
    reference_answer: str
    source_unit_id: str = ""


# --- 题库管理 ---

class QuestionReviewRequest(BaseModel):
    action: str  # approve | reject | offline | edit
    question: str | None = None
    reference_answer: str | None = None
    point_ids: list[str] | None = None  # edit 时整体替换关联知识点


class QuestionPointOut(BaseModel):
    id: str
    title: str


class QuestionOut(BaseModel):
    id: str
    question: str
    reference_answer: str
    category: str
    source_unit_id: str
    source_type: str
    status: str
    usage_count: int
    reviewer_id: str
    reviewer_name: str = ""
    reviewed_at: datetime | None
    created_at: datetime
    points: list[QuestionPointOut] = Field(default_factory=list)

    class Config:
        from_attributes = True


class QuestionListResponse(BaseModel):
    total: int
    items: list[QuestionOut]


# --- 挖掘 ---

class MineRequest(BaseModel):
    limit: int = 20
