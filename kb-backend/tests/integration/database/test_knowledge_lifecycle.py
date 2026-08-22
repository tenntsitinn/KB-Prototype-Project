import pytest
from sqlalchemy import select

from app.models.knowledge_unit import KnowledgeUnit, UnitPermission, UnitStatus
from app.models.user import User
from app.services.importer import knowledge_service


pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_soft_delete_hides_unit_and_restore_makes_it_visible(db_session, monkeypatch):
    monkeypatch.setattr(knowledge_service, "_delete_milvus_vectors", lambda unit_id: None)
    unit = KnowledgeUnit(id="lifecycle-unit", title="Lifecycle", status=UnitStatus.PUBLISHED)
    db_session.add(unit)
    await db_session.commit()

    assert await knowledge_service.soft_delete_knowledge_unit(db_session, unit.id)
    assert await knowledge_service.get_knowledge_unit(db_session, unit.id) is None

    deleted, total = await knowledge_service.list_knowledge_units(db_session, status="deleted")
    assert total == 1
    assert deleted[0].id == unit.id

    assert await knowledge_service.restore_knowledge_unit(db_session, unit.id)
    restored = await knowledge_service.get_knowledge_unit(db_session, unit.id)
    assert restored is not None
    assert restored.status == UnitStatus.DRAFT
    assert restored.deleted_at is None


@pytest.mark.asyncio
async def test_data_permissions_cover_global_department_and_user(db_session):
    user = User(id="permission-user", username="permission-user", password_hash="unused", department_id="dept-a")
    units = [KnowledgeUnit(id=f"permission-unit-{index}", title=f"Unit {index}") for index in range(4)]
    db_session.add_all([user, *units])
    db_session.add_all(
        [
            UnitPermission(unit_id=units[0].id, target_type="global", target_id=""),
            UnitPermission(unit_id=units[1].id, target_type="department", target_id="dept-a"),
            UnitPermission(unit_id=units[2].id, target_type="user", target_id=user.id),
            UnitPermission(unit_id=units[3].id, target_type="department", target_id="dept-b"),
        ]
    )
    await db_session.commit()

    authorized, unauthorized = await knowledge_service.check_unit_permissions(
        db_session, user.id, [unit.id for unit in units]
    )

    assert set(authorized) == {units[0].id, units[1].id, units[2].id}
    assert unauthorized == [units[3].id]


@pytest.mark.asyncio
async def test_transaction_fixture_rolls_back_committed_rows_part_one(db_session):
    db_session.add(User(id="rollback-user", username="rollback-proof", password_hash="unused"))
    await db_session.commit()
    assert await db_session.scalar(select(User).where(User.username == "rollback-proof")) is not None


@pytest.mark.asyncio
async def test_transaction_fixture_rolls_back_committed_rows_part_two(db_session):
    # This uses the same unique values as the previous test. It can commit only
    # when the previous test's outer transaction was fully rolled back.
    assert await db_session.scalar(select(User).where(User.username == "rollback-proof")) is None
    db_session.add(User(id="rollback-user", username="rollback-proof", password_hash="unused"))
    await db_session.commit()
