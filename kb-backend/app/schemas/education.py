"""教培扩展 Pydantic schema：课程、章节、知识点、掌握度。"""
from datetime import datetime

from pydantic import BaseModel


# --- Course ---

class CourseCreate(BaseModel):
    title: str
    description: str = ""


class CourseUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: str | None = None
    sort_order: int | None = None


class CourseOut(BaseModel):
    id: str
    title: str
    description: str
    cover_image: str
    status: str
    sort_order: int
    creator_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CourseListResponse(BaseModel):
    total: int
    items: list[CourseOut]


# --- Chapter ---

class ChapterCreate(BaseModel):
    course_id: str
    parent_id: str | None = None
    title: str
    sort_order: int = 0


class ChapterUpdate(BaseModel):
    title: str | None = None
    parent_id: str | None = None
    sort_order: int | None = None


class ChapterOut(BaseModel):
    id: str
    course_id: str
    parent_id: str | None
    title: str
    sort_order: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ChapterTreeResponse(BaseModel):
    chapter: ChapterOut
    children: list["ChapterTreeResponse"] = []


# --- KnowledgePoint ---

class KnowledgePointCreate(BaseModel):
    unit_id: str
    title: str
    summary: str = ""
    point_type: str = "concept"
    sort_order: int = 0


class KnowledgePointUpdate(BaseModel):
    title: str | None = None
    summary: str | None = None
    point_type: str | None = None
    sort_order: int | None = None


class KnowledgePointOut(BaseModel):
    id: str
    unit_id: str
    title: str
    summary: str
    point_type: str
    sort_order: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class KnowledgePointListResponse(BaseModel):
    total: int
    items: list[KnowledgePointOut]


# --- Mastery ---

class MasteryRecordOut(BaseModel):
    id: str
    user_id: str
    point_id: str
    mastery_level: int
    total_questions: int
    correct_count: int
    last_assessed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MasterySummary(BaseModel):
    point_id: str
    point_title: str
    mastery_level: int
    total_questions: int
    correct_count: int


class MasteryListResponse(BaseModel):
    user_id: str
    items: list[MasterySummary]
