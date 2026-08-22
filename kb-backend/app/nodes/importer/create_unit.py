"""创建知识单元记录节点"""
import os
import logging
from app.core.database import AsyncSessionLocal
from app.graphs.import_graph import ImportState
from app.services.importer.knowledge_service import create_knowledge_unit
from app.schemas.knowledge import KnowledgeUnitCreate

logger = logging.getLogger(__name__)


async def node_create_unit(state: ImportState) -> dict:
    async with AsyncSessionLocal() as db:
        unit = await create_knowledge_unit(db, KnowledgeUnitCreate(
            title=os.path.splitext(state["filename"])[0],
            source_file_name=state["filename"],
            file_type=state["file_type"],
            file_size=state["file_size"],
            file_md5=state["file_md5"],
            creator_id=state["creator_id"],
            category=state.get("category", ""),
        ))
        unit_id = unit.id
        unit_code = unit.unit_code

    return {"unit_id": unit_id, "unit_code": unit_code, "progress": 25, "stage": "unit_created"}