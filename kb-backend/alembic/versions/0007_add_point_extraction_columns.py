"""Add knowledge point extraction columns.

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("knowledge_points", sa.Column("content", sa.Text, server_default="", nullable=False))
    op.add_column("knowledge_points", sa.Column("status", sa.String(16), server_default="pending_review", nullable=False))
    op.add_column("knowledge_points", sa.Column("candidate_merge_json", sa.Text, server_default="[]", nullable=False))
    op.add_column("knowledge_points", sa.Column("source_refs_json", sa.Text, server_default="[]", nullable=False))
    op.add_column("knowledge_points", sa.Column("reviewer_id", sa.String(32), server_default="", nullable=False))
    op.add_column("knowledge_points", sa.Column("reviewed_at", sa.DateTime, nullable=True))
    op.create_index("idx_kp_status", "knowledge_points", ["status"])
    op.add_column("knowledge_units", sa.Column("points_status", sa.String(16), server_default="none", nullable=False))


def downgrade() -> None:
    op.drop_column("knowledge_units", "points_status")
    op.drop_index("idx_kp_status", table_name="knowledge_points")
    op.drop_column("knowledge_points", "reviewed_at")
    op.drop_column("knowledge_points", "reviewer_id")
    op.drop_column("knowledge_points", "source_refs_json")
    op.drop_column("knowledge_points", "candidate_merge_json")
    op.drop_column("knowledge_points", "status")
    op.drop_column("knowledge_points", "content")
