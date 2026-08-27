"""Initial schema: create all tables and indexes.

Revision ID: 0001
Revises:
Create Date: 2026-08-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "knowledge_units",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("unit_code", sa.String(64), unique=True, nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("content", sa.Text, server_default=""),
        sa.Column("summary", sa.Text, server_default=""),
        sa.Column("category", sa.String(128), server_default=""),
        sa.Column("source_file_name", sa.String(512), server_default=""),
        sa.Column("file_type", sa.String(16), server_default=""),
        sa.Column("file_size", sa.Integer, server_default="0"),
        sa.Column("file_md5", sa.String(64), server_default=""),
        sa.Column("minio_path", sa.String(1024), server_default=""),
        sa.Column("status", sa.String(16), server_default="draft"),
        sa.Column("creator_id", sa.String(32), server_default=""),
        sa.Column("deleted_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "unit_permissions",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("unit_id", sa.String(32), sa.ForeignKey("knowledge_units.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_type", sa.String(16), nullable=False),
        sa.Column("target_id", sa.String(64), server_default=""),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "qa_access_logs",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("session_id", sa.String(64), nullable=False),
        sa.Column("user_id", sa.String(32), nullable=False),
        sa.Column("question", sa.Text, server_default=""),
        sa.Column("answer", sa.Text, server_default=""),
        sa.Column("recalled_unit_ids_json", sa.Text, server_default="[]"),
        sa.Column("authorized_unit_ids_json", sa.Text, server_default="[]"),
        sa.Column("unauthorized_unit_ids_json", sa.Text, server_default="[]"),
        sa.Column("prompt_tokens", sa.Integer, server_default="0"),
        sa.Column("completion_tokens", sa.Integer, server_default="0"),
        sa.Column("total_tokens", sa.Integer, server_default="0"),
        sa.Column("response_time_ms", sa.Integer, server_default="0"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "faqs",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("question", sa.Text, nullable=False),
        sa.Column("answer", sa.Text, server_default=""),
        sa.Column("related_unit_id", sa.String(32), server_default=""),
        sa.Column("source_type", sa.String(16), server_default="manual"),
        sa.Column("status", sa.String(16), server_default="pending_review"),
        sa.Column("hit_count", sa.Integer, server_default="0"),
        sa.Column("reviewer_id", sa.String(32), server_default=""),
        sa.Column("reviewed_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "tags",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("name", sa.String(128), unique=True, nullable=False),
        sa.Column("sort_order", sa.Integer, server_default="0"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "knowledge_chunks",
        sa.Column("unit_id", sa.String(32), primary_key=True),
        sa.Column("chunk_index", sa.Integer, primary_key=True),
        sa.Column("chunk_text", sa.Text, server_default=""),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "quiz_questions",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("question", sa.Text, nullable=False),
        sa.Column("reference_answer", sa.Text, server_default=""),
        sa.Column("category", sa.String(128), server_default=""),
        sa.Column("source_unit_id", sa.String(32), server_default=""),
        sa.Column("source_type", sa.String(16), server_default="ai_generated"),
        sa.Column("status", sa.String(16), server_default="pending_review"),
        sa.Column("usage_count", sa.Integer, server_default="0"),
        sa.Column("reviewer_id", sa.String(32), server_default=""),
        sa.Column("reviewed_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "quiz_answers",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("question_id", sa.String(32), nullable=False),
        sa.Column("user_id", sa.String(32), nullable=False),
        sa.Column("answer_text", sa.Text, server_default=""),
        sa.Column("score", sa.Integer, server_default="0"),
        sa.Column("feedback", sa.Text, server_default=""),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "knowledge_gaps",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("question_pattern", sa.Text, server_default=""),
        sa.Column("sample_questions_json", sa.Text, server_default="[]"),
        sa.Column("ask_count", sa.Integer, server_default="0"),
        sa.Column("last_asked_at", sa.DateTime, nullable=True),
        sa.Column("status", sa.String(16), server_default="unresolved"),
        sa.Column("resolved_unit_id", sa.String(32), server_default=""),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "users",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("username", sa.String(64), unique=True, nullable=False),
        sa.Column("password_hash", sa.String(256), nullable=False),
        sa.Column("display_name", sa.String(128), server_default=""),
        sa.Column("email", sa.String(128), server_default=""),
        sa.Column("department_id", sa.String(32), server_default=""),
        sa.Column("status", sa.String(16), server_default="active"),
        sa.Column("is_superuser", sa.Boolean, server_default=sa.false()),
        sa.Column("llm_api_key", sa.String(256), server_default=""),
        sa.Column("last_login_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "departments",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("parent_id", sa.String(32), nullable=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("leader_id", sa.String(32), server_default=""),
        sa.Column("sort_order", sa.Integer, server_default="0"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "roles",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("role_name", sa.String(64), nullable=False),
        sa.Column("role_code", sa.String(64), unique=True, nullable=False),
        sa.Column("description", sa.String(256), server_default=""),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "user_roles",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("user_id", sa.String(32), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role_id", sa.String(32), sa.ForeignKey("roles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "role_permissions",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("role_id", sa.String(32), sa.ForeignKey("roles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("permission_code", sa.String(64), nullable=False),
        sa.Column("permission_type", sa.String(16), server_default="operation"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_index("idx_ku_status", "knowledge_units", ["status"])
    op.create_index("idx_ku_category", "knowledge_units", ["category"])
    op.create_index("idx_ku_creator", "knowledge_units", ["creator_id"])
    op.create_index("idx_up_unit_id", "unit_permissions", ["unit_id"])
    op.create_index("idx_up_target", "unit_permissions", ["target_type", "target_id"])
    op.create_index("idx_qa_user_id", "qa_access_logs", ["user_id"])
    op.create_index("idx_qa_session", "qa_access_logs", ["session_id"])
    op.create_index("idx_qa_created", "qa_access_logs", ["created_at"])
    op.create_index("idx_faq_status", "faqs", ["status"])
    op.create_index("idx_gap_status", "knowledge_gaps", ["status"])
    op.create_index("idx_quiz_status", "quiz_questions", ["status"])
    op.create_index("idx_quiz_category", "quiz_questions", ["category"])
    op.create_index("idx_quiz_answer_question", "quiz_answers", ["question_id"])
    op.create_index("idx_quiz_answer_user", "quiz_answers", ["user_id"])


def downgrade() -> None:
    op.drop_index("idx_quiz_answer_user", table_name="quiz_answers")
    op.drop_index("idx_quiz_answer_question", table_name="quiz_answers")
    op.drop_index("idx_quiz_category", table_name="quiz_questions")
    op.drop_index("idx_quiz_status", table_name="quiz_questions")
    op.drop_index("idx_gap_status", table_name="knowledge_gaps")
    op.drop_index("idx_faq_status", table_name="faqs")
    op.drop_index("idx_qa_created", table_name="qa_access_logs")
    op.drop_index("idx_qa_session", table_name="qa_access_logs")
    op.drop_index("idx_qa_user_id", table_name="qa_access_logs")
    op.drop_index("idx_up_target", table_name="unit_permissions")
    op.drop_index("idx_up_unit_id", table_name="unit_permissions")
    op.drop_index("idx_ku_creator", table_name="knowledge_units")
    op.drop_index("idx_ku_category", table_name="knowledge_units")
    op.drop_index("idx_ku_status", table_name="knowledge_units")

    op.drop_table("role_permissions")
    op.drop_table("user_roles")
    op.drop_table("roles")
    op.drop_table("departments")
    op.drop_table("users")
    op.drop_table("knowledge_gaps")
    op.drop_table("quiz_answers")
    op.drop_table("quiz_questions")
    op.drop_table("knowledge_chunks")
    op.drop_table("tags")
    op.drop_table("faqs")
    op.drop_table("qa_access_logs")
    op.drop_table("unit_permissions")
    op.drop_table("knowledge_units")
