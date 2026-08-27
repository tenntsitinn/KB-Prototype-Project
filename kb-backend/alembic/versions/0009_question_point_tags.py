"""题目关联知识点标签（多对多）

Revision ID: 0009
Revises: 0008
"""
from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "quiz_question_points",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("question_id", sa.String(32), sa.ForeignKey("quiz_questions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("point_id", sa.String(32), sa.ForeignKey("knowledge_points.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("question_id", "point_id", name="uq_question_point"),
    )
    op.create_index("ix_qqp_question_id", "quiz_question_points", ["question_id"])
    op.create_index("ix_qqp_point_id", "quiz_question_points", ["point_id"])

    # 回填 1：历史单点关联 source_point_id（跳过悬空引用）
    op.execute(sa.text("""
        INSERT INTO quiz_question_points (id, question_id, point_id)
        SELECT md5(q.id || ':sp:' || q.source_point_id), q.id, q.source_point_id
        FROM quiz_questions q
        WHERE q.source_point_id IS NOT NULL AND q.source_point_id <> ''
          AND EXISTS (SELECT 1 FROM knowledge_points kp WHERE kp.id = q.source_point_id)
        ON CONFLICT DO NOTHING
    """))
    # 回填 2：有来源文档的题目挂上该文档全部已确认知识点
    op.execute(sa.text("""
        INSERT INTO quiz_question_points (id, question_id, point_id)
        SELECT md5(q.id || ':up:' || kp.id), q.id, kp.id
        FROM quiz_questions q
        JOIN knowledge_points kp ON kp.unit_id = q.source_unit_id AND kp.status = 'confirmed'
        WHERE q.source_unit_id <> ''
        ON CONFLICT DO NOTHING
    """))


def downgrade() -> None:
    op.drop_index("ix_qqp_point_id", table_name="quiz_question_points")
    op.drop_index("ix_qqp_question_id", table_name="quiz_question_points")
    op.drop_table("quiz_question_points")
