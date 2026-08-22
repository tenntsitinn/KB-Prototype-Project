import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, RequirePermission
from app.core.permissions import UserPermissions, PERM_GAP_MANAGE
from app.models.knowledge_unit import GapStatus
from app.schemas.gap import (
    KnowledgeGapOut,
    KnowledgeGapListResponse,
    ResolveGapRequest,
)
from app.services.rag import gap_service

router = APIRouter(prefix="/api/settlement", tags=["知识沉淀"])


@router.get("/knowledge-gaps", response_model=KnowledgeGapListResponse)
async def list_gaps(
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: str = Query("", description="unresolved | resolved | ignored"),
    db: AsyncSession = Depends(get_db),
    _: UserPermissions = Depends(RequirePermission(PERM_GAP_MANAGE)),
):
    """查询知识缺口列表"""

    gap_status = None
    if status:
        try:
            gap_status = GapStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"无效状态: {status}")

    items, total = await gap_service.list_gaps(db, offset, limit, gap_status)
    return KnowledgeGapListResponse(
        total=total,
        items=[
            KnowledgeGapOut(
                id=g.id,
                question_pattern=g.question_pattern,
                sample_questions=json.loads(g.sample_questions_json) if g.sample_questions_json else [],
                ask_count=g.ask_count,
                last_asked_at=g.last_asked_at,
                status=g.status,
                resolved_unit_id=g.resolved_unit_id,
                created_at=g.created_at,
            )
            for g in items
        ],
    )


@router.post("/knowledge-gaps/{gap_id}/resolve")
async def resolve_gap(
    gap_id: str,
    request: ResolveGapRequest = ResolveGapRequest(),
    db: AsyncSession = Depends(get_db),
    _: UserPermissions = Depends(RequirePermission(PERM_GAP_MANAGE)),
):

    gap = await gap_service.resolve_gap(db, gap_id, request.unit_id)
    if not gap:
        raise HTTPException(status_code=404, detail="缺口不存在")

    return {
        "id": gap.id,
        "status": gap.status,
        "resolved_unit_id": gap.resolved_unit_id,
    }


@router.post("/knowledge-gaps/{gap_id}/ignore")
async def ignore_gap(
    gap_id: str,
    db: AsyncSession = Depends(get_db),
    _: UserPermissions = Depends(RequirePermission(PERM_GAP_MANAGE)),
):

    gap = await gap_service.ignore_gap(db, gap_id)
    if not gap:
        raise HTTPException(status_code=404, detail="缺口不存在")

    return {"id": gap.id, "status": gap.status}