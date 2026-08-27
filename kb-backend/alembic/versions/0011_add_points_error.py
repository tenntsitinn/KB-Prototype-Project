"""add points_error to knowledge_units

Revision ID: 0011
Revises: 0010
"""
from alembic import op
import sqlalchemy as sa

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("knowledge_units", sa.Column("points_error", sa.Text(), server_default="", nullable=False))


def downgrade() -> None:
    op.drop_column("knowledge_units", "points_error")
