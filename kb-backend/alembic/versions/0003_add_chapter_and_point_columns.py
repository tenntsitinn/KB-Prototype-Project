"""Add chapter_id, app_mode to knowledge_units; source_point_id to quiz_questions.

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("knowledge_units", sa.Column("chapter_id", sa.String(32), nullable=True))
    op.add_column("knowledge_units", sa.Column("app_mode", sa.String(16), server_default="shared"))
    op.create_index("idx_ku_chapter_id", "knowledge_units", ["chapter_id"])

    op.add_column("quiz_questions", sa.Column("source_point_id", sa.String(32), nullable=True))
    op.create_index("idx_qq_source_point", "quiz_questions", ["source_point_id"])


def downgrade() -> None:
    op.drop_index("idx_qq_source_point", table_name="quiz_questions")
    op.drop_column("quiz_questions", "source_point_id")
    op.drop_index("idx_ku_chapter_id", table_name="knowledge_units")
    op.drop_column("knowledge_units", "app_mode")
    op.drop_column("knowledge_units", "chapter_id")
