"""Add education tables: courses, chapters, knowledge_points, mastery_records.

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "courses",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("description", sa.Text, server_default=""),
        sa.Column("cover_image", sa.String(512), server_default=""),
        sa.Column("status", sa.String(16), server_default="active"),
        sa.Column("sort_order", sa.Integer, server_default="0"),
        sa.Column("creator_id", sa.String(32), server_default=""),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "chapters",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("course_id", sa.String(32), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("parent_id", sa.String(32), nullable=True),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("sort_order", sa.Integer, server_default="0"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("idx_chapter_course_id", "chapters", ["course_id"])

    op.create_table(
        "knowledge_points",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("unit_id", sa.String(32), sa.ForeignKey("knowledge_units.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("summary", sa.Text, server_default=""),
        sa.Column("point_type", sa.String(16), server_default="concept"),
        sa.Column("source_chunk_indices", sa.Text, server_default="[]"),
        sa.Column("sort_order", sa.Integer, server_default="0"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("idx_kp_unit_id", "knowledge_points", ["unit_id"])

    op.create_table(
        "mastery_records",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("user_id", sa.String(32), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("point_id", sa.String(32), sa.ForeignKey("knowledge_points.id", ondelete="CASCADE"), nullable=False),
        sa.Column("mastery_level", sa.Integer, server_default="0"),
        sa.Column("total_questions", sa.Integer, server_default="0"),
        sa.Column("correct_count", sa.Integer, server_default="0"),
        sa.Column("last_assessed_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "point_id", name="uq_mastery_user_point"),
    )
    op.create_index("idx_mr_user_id", "mastery_records", ["user_id"])
    op.create_index("idx_mr_point_id", "mastery_records", ["point_id"])


def downgrade() -> None:
    op.drop_index("idx_mr_point_id", table_name="mastery_records")
    op.drop_index("idx_mr_user_id", table_name="mastery_records")
    op.drop_table("mastery_records")
    op.drop_index("idx_kp_unit_id", table_name="knowledge_points")
    op.drop_table("knowledge_points")
    op.drop_index("idx_chapter_course_id", table_name="chapters")
    op.drop_table("chapters")
    op.drop_table("courses")
