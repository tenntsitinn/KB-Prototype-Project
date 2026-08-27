"""Unify FAQ into quiz_questions settlement pool.

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # FAQ 数据并入题库沉淀池：question/answer/related_unit_id/hit_count 逐字段映射
    op.execute("""
        INSERT INTO quiz_questions
            (id, question, reference_answer, category, source_unit_id, source_point_id,
             source_type, status, usage_count, reviewer_id, reviewed_at, created_at, updated_at)
        SELECT
            f.id, f.question, f.answer, '', f.related_unit_id, NULL,
            f.source_type, f.status, f.hit_count, f.reviewer_id, f.reviewed_at,
            f.created_at, f.updated_at
        FROM faqs f
        WHERE NOT EXISTS (SELECT 1 FROM quiz_questions q WHERE q.id = f.id)
    """)
    op.drop_table("faqs")


def downgrade() -> None:
    op.create_table(
        "faqs",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("question", sa.Text, nullable=False),
        sa.Column("answer", sa.Text, server_default="", nullable=False),
        sa.Column("related_unit_id", sa.String(32), server_default="", nullable=False),
        sa.Column("source_type", sa.String(16), server_default="manual", nullable=False),
        sa.Column("status", sa.String(16), server_default="pending_review", nullable=False),
        sa.Column("hit_count", sa.Integer, server_default="0", nullable=False),
        sa.Column("reviewer_id", sa.String(32), server_default="", nullable=False),
        sa.Column("reviewed_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
    )
    op.execute("""
        INSERT INTO faqs
            (id, question, answer, related_unit_id, source_type, status, hit_count,
             reviewer_id, reviewed_at, created_at, updated_at)
        SELECT
            q.id, q.question, q.reference_answer, q.source_unit_id, q.source_type, q.status,
            q.usage_count, q.reviewer_id, q.reviewed_at, q.created_at, q.updated_at
        FROM quiz_questions q
        WHERE q.source_type IN ('auto_mined', 'manual')
          AND NOT EXISTS (SELECT 1 FROM faqs f WHERE f.id = q.id)
    """)
