from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.dependencies import get_db, get_current_user, RequirePermission
from app.core.permissions import UserPermissions, PERM_FAQ_MANAGE
from app.models.user import User
from app.schemas.faq import (
    FAQRecommendationOut,
    FAQRecommendationListResponse,
    FAQReviewRequest,
    FAQPublishedOut,
    FAQPublishedListResponse,
)
from app.services.rag import faq_service

router = APIRouter(prefix="/api/settlement", tags=["知识沉淀"])


# ---------------------------------------------------------------------------
# FAQ 推荐与审核
# ---------------------------------------------------------------------------

@router.get("/faqs/recommendations", response_model=FAQRecommendationListResponse)
async def list_recommendations(
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: UserPermissions = Depends(RequirePermission(PERM_FAQ_MANAGE)),
):
    """查询自动推荐的待审核 FAQ 列表"""

    items, total = await faq_service.list_recommendations(db, offset, limit)
    return FAQRecommendationListResponse(
        total=total,
        items=[
            FAQRecommendationOut(
                id=f.id,
                question=f.question,
                answer=f.answer,
                related_unit_id=f.related_unit_id,
                source_type=f.source_type,
                status=f.status,
                hit_count=f.hit_count,
                created_at=f.created_at,
            )
            for f in items
        ],
    )


@router.post("/faqs/{faq_id}/review")
async def review_faq(
    faq_id: str,
    request: FAQReviewRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    _: UserPermissions = Depends(RequirePermission(PERM_FAQ_MANAGE)),
):
    """审核 FAQ：approve 发布上线 / reject 驳回"""

    if request.action not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="action 必须是 approve 或 reject")

    faq = await faq_service.review_faq(
        db, faq_id, request.action, user.id, request.edited_answer
    )
    if not faq:
        raise HTTPException(status_code=404, detail="FAQ 不存在")

    return {
        "id": faq.id,
        "question": faq.question,
        "answer": faq.answer,
        "status": faq.status,
        "reviewer_id": faq.reviewer_id,
        "reviewed_at": faq.reviewed_at.isoformat() if faq.reviewed_at else None,
    }


# ---------------------------------------------------------------------------
# 已发布 FAQ 管理
# ---------------------------------------------------------------------------

@router.get("/faqs", response_model=FAQPublishedListResponse)
async def list_published_faqs(
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: UserPermissions = Depends(RequirePermission(PERM_FAQ_MANAGE)),
):
    """查询已发布 FAQ 列表"""

    items, total = await faq_service.list_published_faqs(db, offset, limit)
    return FAQPublishedListResponse(
        total=total,
        items=[
            FAQPublishedOut(
                id=f.id,
                question=f.question,
                answer=f.answer,
                source_type=f.source_type,
                hit_count=f.hit_count,
                reviewer_id=f.reviewer_id,
                reviewed_at=f.reviewed_at,
                created_at=f.created_at,
                updated_at=f.updated_at,
            )
            for f in items
        ],
    )


@router.delete("/faqs/{faq_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_faq(
    faq_id: str,
    db: AsyncSession = Depends(get_db),
    _: UserPermissions = Depends(RequirePermission(PERM_FAQ_MANAGE)),
):
    """删除 FAQ 并清理缓存"""

    deleted = await faq_service.delete_faq(db, faq_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="FAQ 不存在")


@router.put("/faqs/{faq_id}")
async def update_faq(
    faq_id: str,
    request: FAQReviewRequest,
    db: AsyncSession = Depends(get_db),
    _: UserPermissions = Depends(RequirePermission(PERM_FAQ_MANAGE)),
):
    """更新已发布 FAQ 的问题和答案"""

    faq = await faq_service.update_faq(db, faq_id, request.question, request.answer)
    if not faq:
        raise HTTPException(status_code=404, detail="FAQ 不存在")

    return {"id": faq.id, "question": faq.question, "answer": faq.answer}


# ---------------------------------------------------------------------------
# 缓存同步
# ---------------------------------------------------------------------------

@router.post("/faqs/sync-cache")
async def sync_faq_cache(
    db: AsyncSession = Depends(get_db),
    _: UserPermissions = Depends(RequirePermission(PERM_FAQ_MANAGE)),
):
    """全量同步已发布 FAQ 到向量缓存（管理员手动触发）"""

    count = await faq_service.sync_faq_cache(db)
    return {"synced_count": count}