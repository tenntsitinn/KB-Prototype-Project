import uuid
from datetime import datetime
from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, Enum as SAEnum, func, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from enum import Enum


class Base(DeclarativeBase):
    pass


class UnitStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    DELETED = "deleted"
    SEMANTIC_DUPLICATE = "semantic_duplicate"


class TargetType(str, Enum):
    GLOBAL = "global"
    DEPARTMENT = "department"
    ROLE = "role"
    USER = "user"


class QuizQuestionStatus(str, Enum):
    PENDING_REVIEW = "pending_review"
    PUBLISHED = "published"
    REJECTED = "rejected"
    OFFLINE = "offline"


class QuizQuestionSource(str, Enum):
    AI_GENERATED = "ai_generated"
    USER_QUESTION = "user_question"
    AUTO_MINED = "auto_mined"
    MANUAL = "manual"


class GapStatus(str, Enum):
    UNRESOLVED = "unresolved"
    RESOLVED = "resolved"
    IGNORED = "ignored"


def _gen_uuid() -> str:
    return uuid.uuid4().hex[:12]


class KnowledgeUnit(Base):
    __tablename__ = "knowledge_units"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_gen_uuid)
    unit_code: Mapped[str] = mapped_column(String(64), unique=True, default=_gen_uuid)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    content: Mapped[str] = mapped_column(Text, default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(128), default="")
    source_file_name: Mapped[str] = mapped_column(String(512), default="")
    file_type: Mapped[str] = mapped_column(String(16), default="")
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    file_md5: Mapped[str] = mapped_column(String(64), default="")
    minio_path: Mapped[str] = mapped_column(String(1024), default="")
    status: Mapped[str] = mapped_column(String(16), default="draft")
    points_status: Mapped[str] = mapped_column(String(16), default="none")
    points_error: Mapped[str] = mapped_column(Text, default="")
    creator_id: Mapped[str] = mapped_column(String(32), default="")
    chapter_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    app_mode: Mapped[str] = mapped_column(String(16), default="shared")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    permissions: Mapped[list["UnitPermission"]] = relationship(back_populates="unit", cascade="all, delete-orphan")


class UnitPermission(Base):
    __tablename__ = "unit_permissions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_gen_uuid)
    unit_id: Mapped[str] = mapped_column(String(32), ForeignKey("knowledge_units.id"), nullable=False)
    target_type: Mapped[str] = mapped_column(String(16), nullable=False)
    target_id: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    unit: Mapped["KnowledgeUnit"] = relationship(back_populates="permissions")


class QAAccessLog(Base):
    __tablename__ = "qa_access_logs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_gen_uuid)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[str] = mapped_column(String(32), nullable=False)
    question: Mapped[str] = mapped_column(Text, default="")
    answer: Mapped[str] = mapped_column(Text, default="")
    recalled_unit_ids_json: Mapped[str] = mapped_column(Text, default="[]")
    authorized_unit_ids_json: Mapped[str] = mapped_column(Text, default="[]")
    unauthorized_unit_ids_json: Mapped[str] = mapped_column(Text, default="[]")
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    response_time_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_gen_uuid)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class KnowledgeChunk(Base):
    """知识切片持久化：向量化断点续跑的依据，切片在向量化前先落库"""
    __tablename__ = "knowledge_chunks"

    unit_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    chunk_index: Mapped[int] = mapped_column(Integer, primary_key=True)
    chunk_text: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class QuizQuestion(Base):
    __tablename__ = "quiz_questions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_gen_uuid)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    reference_answer: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(128), default="")
    source_unit_id: Mapped[str] = mapped_column(String(32), default="")
    source_point_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_type: Mapped[str] = mapped_column(String(16), default="ai_generated")
    status: Mapped[str] = mapped_column(String(16), default="pending_review")
    usage_count: Mapped[int] = mapped_column(Integer, default=0)
    reviewer_id: Mapped[str] = mapped_column(String(32), default="")
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class QuizQuestionPoint(Base):
    """题目-知识点多对多关联（一道题可挂多个知识点标签）"""
    __tablename__ = "quiz_question_points"
    __table_args__ = (UniqueConstraint("question_id", "point_id", name="uq_question_point"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_gen_uuid)
    question_id: Mapped[str] = mapped_column(String(32), ForeignKey("quiz_questions.id", ondelete="CASCADE"), nullable=False)
    point_id: Mapped[str] = mapped_column(String(32), ForeignKey("knowledge_points.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class QuizAnswer(Base):
    __tablename__ = "quiz_answers"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_gen_uuid)
    question_id: Mapped[str] = mapped_column(String(32), nullable=False)
    user_id: Mapped[str] = mapped_column(String(32), nullable=False)
    answer_text: Mapped[str] = mapped_column(Text, default="")
    score: Mapped[int] = mapped_column(Integer, default=0)
    feedback: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class KnowledgeGap(Base):
    __tablename__ = "knowledge_gaps"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_gen_uuid)
    question_pattern: Mapped[str] = mapped_column(Text, default="")
    sample_questions_json: Mapped[str] = mapped_column(Text, default="[]")
    ask_count: Mapped[int] = mapped_column(Integer, default=0)
    last_asked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="unresolved")
    resolved_unit_id: Mapped[str] = mapped_column(String(32), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
