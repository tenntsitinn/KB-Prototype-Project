"""Data migration: create default knowledge_points for existing units, link quiz_questions.

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-23

"""
import uuid
from typing import Sequence, Union

from alembic import op, context
import sqlalchemy as sa


revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if context.is_offline_mode():
        return

    conn = op.get_bind()

    units = conn.execute(sa.text(
        "SELECT id, title FROM knowledge_units "
        "WHERE id NOT IN (SELECT DISTINCT unit_id FROM knowledge_points)"
    )).fetchall()

    for unit_id, title in units:
        point_id = uuid.uuid4().hex[:12]
        conn.execute(sa.text(
            "INSERT INTO knowledge_points (id, unit_id, title, summary, point_type, "
            "source_chunk_indices, sort_order) "
            "VALUES (:id, :unit_id, :title, '', 'concept', '[]', 0)"
        ), {"id": point_id, "unit_id": unit_id, "title": title})

        conn.execute(sa.text(
            "UPDATE quiz_questions SET source_point_id = :point_id "
            "WHERE source_unit_id = :unit_id AND source_point_id IS NULL"
        ), {"point_id": point_id, "unit_id": unit_id})


def downgrade() -> None:
    if context.is_offline_mode():
        return

    conn = op.get_bind()
    conn.execute(sa.text("UPDATE quiz_questions SET source_point_id = NULL"))
    conn.execute(sa.text(
        "DELETE FROM knowledge_points WHERE id IN ("
        "  SELECT kp.id FROM knowledge_points kp "
        "  JOIN knowledge_units ku ON kp.unit_id = ku.id "
        "  WHERE kp.title = ku.title"
        ")"
    ))
