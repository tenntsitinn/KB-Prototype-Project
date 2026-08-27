"""Add education roles: teacher, student, personal_user and permission codes.

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-23

"""
import uuid
from typing import Sequence, Union

from alembic import op, context
import sqlalchemy as sa


revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if context.is_offline_mode():
        return

    conn = op.get_bind()

    roles = [
        ("teacher", "教师", "教培版教师角色"),
        ("student", "学员", "教培版学员角色"),
        ("personal_user", "个人用户", "个人版用户角色"),
    ]
    role_ids: dict[str, str] = {}
    for code, name, desc in roles:
        rid = uuid.uuid4().hex[:12]
        conn.execute(sa.text(
            "INSERT INTO roles (id, role_name, role_code, description) "
            "VALUES (:id, :name, :code, :desc)"
        ), {"id": rid, "name": name, "code": code, "desc": desc})
        role_ids[code] = rid

    teacher_permissions = [
        ("course:manage", "operation"),
        ("course:read", "operation"),
        ("quiz:review", "operation"),
        ("mastery:view_all", "operation"),
    ]
    student_permissions = [
        ("course:read", "operation"),
        ("quiz:answer", "operation"),
        ("mastery:view", "operation"),
    ]

    for code, ptype in teacher_permissions:
        conn.execute(sa.text(
            "INSERT INTO role_permissions (id, role_id, permission_code, permission_type) "
            "VALUES (:id, :role_id, :code, :ptype)"
        ), {"id": uuid.uuid4().hex[:12], "role_id": role_ids["teacher"], "code": code, "ptype": ptype})

    for code, ptype in student_permissions:
        conn.execute(sa.text(
            "INSERT INTO role_permissions (id, role_id, permission_code, permission_type) "
            "VALUES (:id, :role_id, :code, :ptype)"
        ), {"id": uuid.uuid4().hex[:12], "role_id": role_ids["student"], "code": code, "ptype": ptype})


def downgrade() -> None:
    if context.is_offline_mode():
        return

    conn = op.get_bind()
    conn.execute(sa.text(
        "DELETE FROM role_permissions WHERE permission_code IN "
        "('course:manage','course:read','quiz:answer','quiz:review','mastery:view','mastery:view_all')"
    ))
    conn.execute(sa.text(
        "DELETE FROM roles WHERE role_code IN ('teacher','student','personal_user')"
    ))
