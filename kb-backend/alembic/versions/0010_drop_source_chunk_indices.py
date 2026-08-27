"""删除 knowledge_points.source_chunk_indices 死列

Revision ID: 0010
Revises: 0009
"""
from alembic import op
import sqlalchemy as sa

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("knowledge_points", "source_chunk_indices")


def downgrade() -> None:
    op.add_column("knowledge_points", sa.Column("source_chunk_indices", sa.Text(), server_default="[]", nullable=False))
