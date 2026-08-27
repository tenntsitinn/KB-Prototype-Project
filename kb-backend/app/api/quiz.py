from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, get_current_user, RequirePermission
from app.core.permissions import UserPermissions, PERM_QUIZ_MANAGE
from app.models.user import User
from app.schemas.quiz import (
    NextQuestionRequest, NextQuestionResponse,
    AnswerRequest, AnswerResponse,
    QuestionReviewRequest, QuestionOut, QuestionListResponse,
    MineRequest,
)
from app.services import quiz_service
from app.services.quiz_service import InsufficientBalanceError

router = APIRouter(prefix="/api/quiz", tags=["智能出题"])


# ---------------------------------------------------------------------------
# 出题（登录即可用）
# ---------------------------------------------------------------------------

@router.post("/next", response_model=NextQuestionResponse)
async def next_question(
    req: NextQuestionRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """出一道题：题库命中优先，未命中实时生成。支持按标签或按文档出题。"""
    try:
        result = await quiz_service.next_question(
            db, user, req.category, req.asked_question_ids,
            req.source_unit_id, req.source_unit_ids,
        )
    except InsufficientBalanceError:
        raise HTTPException(status_code=402, detail="402 Insufficient Balance : 余额不足")
    if not result:
        raise HTTPException(status_code=404, detail="所选范围内暂无可出题的内容")
    return NextQuestionResponse(
        question_id=result["question_id"],
        question=result["question"],
        from_bank=result["from_bank"],
        source_unit_id=result.get("source_unit_id", ""),
        reference_answer=result.get("reference_answer", ""),
    )


# ---------------------------------------------------------------------------
# 判分（登录即可用）
# ---------------------------------------------------------------------------

@router.post("/answer", response_model=AnswerResponse)
async def submit_answer(
    req: AnswerRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """提交作答，返回判分 + 参考答案"""
    try:
        result = await quiz_service.grade_and_record(db, user, req.question_id, req.answer_text)
    except InsufficientBalanceError:
        raise HTTPException(status_code=402, detail="402 Insufficient Balance : 余额不足")
    if not result:
        raise HTTPException(status_code=404, detail="题目不存在或无权作答")
    return AnswerResponse(
        question_id=result["question_id"],
        question=result["question"],
        score=result["score"],
        feedback=result["feedback"],
        reference_answer=result["reference_answer"],
        source_unit_id=result.get("source_unit_id", ""),
    )


# ---------------------------------------------------------------------------
# 题库管理（需 quiz:manage 权限）
# ---------------------------------------------------------------------------

@router.get("/bank", response_model=QuestionListResponse)
async def list_bank(
    status: str = Query(default=""),
    review_status: str = Query(default="", description="审核状态：pending=待审核 reviewed=已审核"),
    category: str = Query(default=""),
    keyword: str = Query(default="", description="题目/参考答案关键词"),
    source_type: str = Query(default=""),
    course_id: str = Query(default=""),
    chapter_id: str = Query(default=""),
    point_id: str = Query(default=""),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: UserPermissions = Depends(RequirePermission(PERM_QUIZ_MANAGE)),
):
    """题库列表（状态/审核状态/来源/课程-章节-知识点/关键词筛选）"""
    from sqlalchemy import select, func, or_, text
    from app.models.knowledge_unit import QuizQuestion, QuizQuestionPoint, KnowledgeUnit
    from app.models.education import KnowledgePoint, Chapter
    from app.models.user import User

    stmt = select(QuizQuestion)
    if status:
        stmt = stmt.where(QuizQuestion.status == status)
    elif review_status == "pending":
        stmt = stmt.where(QuizQuestion.status == "pending_review")
    elif review_status == "reviewed":
        stmt = stmt.where(QuizQuestion.status != "pending_review")
    if category:
        stmt = stmt.where(QuizQuestion.category == category)
    if source_type:
        stmt = stmt.where(QuizQuestion.source_type == source_type)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(or_(
            QuizQuestion.question.ilike(like),
            QuizQuestion.reference_answer.ilike(like),
        ))

    # 三级分类筛选：知识点 > 章节 > 课程（任一级命中即可，兼容旧数据的来源文档路径）
    if point_id:
        point_unit = select(KnowledgePoint.unit_id).where(KnowledgePoint.id == point_id)
        stmt = stmt.where(or_(
            QuizQuestion.source_point_id == point_id,
            QuizQuestion.source_unit_id.in_(point_unit),
            QuizQuestion.id.in_(
                select(QuizQuestionPoint.question_id).where(QuizQuestionPoint.point_id == point_id)
            ),
        ))
    elif chapter_id:
        tree_result = await db.execute(text("""
            WITH RECURSIVE ct AS (
                SELECT id FROM chapters WHERE id = :cid
                UNION ALL
                SELECT c.id FROM chapters c JOIN ct ON c.parent_id = ct.id
            )
            SELECT id FROM ct
        """), {"cid": chapter_id})
        chapter_ids = [r[0] for r in tree_result.all()]
        if chapter_ids:
            unit_ids = select(KnowledgeUnit.id).where(KnowledgeUnit.chapter_id.in_(chapter_ids))
            stmt = stmt.where(or_(
                QuizQuestion.source_unit_id.in_(unit_ids),
                QuizQuestion.id.in_(
                    select(QuizQuestionPoint.question_id)
                    .join(KnowledgePoint, KnowledgePoint.id == QuizQuestionPoint.point_id)
                    .where(KnowledgePoint.unit_id.in_(unit_ids))
                ),
            ))
        else:
            stmt = stmt.where(QuizQuestion.id == "__none__")
    elif course_id:
        course_chapters = select(Chapter.id).where(Chapter.course_id == course_id)
        unit_ids = select(KnowledgeUnit.id).where(KnowledgeUnit.chapter_id.in_(course_chapters))
        stmt = stmt.where(or_(
            QuizQuestion.source_unit_id.in_(unit_ids),
            QuizQuestion.id.in_(
                select(QuizQuestionPoint.question_id)
                .join(KnowledgePoint, KnowledgePoint.id == QuizQuestionPoint.point_id)
                .where(KnowledgePoint.unit_id.in_(unit_ids))
            ),
        ))

    total_result = await db.execute(select(func.count()).select_from(stmt.subquery()))
    total = total_result.scalar() or 0

    items_result = await db.execute(
        stmt.order_by(QuizQuestion.created_at.desc()).offset(offset).limit(limit)
    )
    items = items_result.scalars().all()

    reviewer_ids = {q.reviewer_id for q in items if q.reviewer_id}
    reviewer_names: dict[str, str] = {}
    if reviewer_ids:
        u_result = await db.execute(
            select(User.id, User.display_name, User.username).where(User.id.in_(reviewer_ids))
        )
        for uid, display_name, username in u_result.all():
            reviewer_names[uid] = display_name or username

    # 关联知识点标签（排除已驳回的知识点）
    qids = [q.id for q in items]
    points_map: dict[str, list[dict]] = {}
    if qids:
        p_result = await db.execute(
            select(QuizQuestionPoint.question_id, KnowledgePoint.id, KnowledgePoint.title)
            .join(KnowledgePoint, KnowledgePoint.id == QuizQuestionPoint.point_id)
            .where(
                QuizQuestionPoint.question_id.in_(qids),
                KnowledgePoint.status != "rejected",
            )
            .order_by(KnowledgePoint.title)
        )
        for qid, pid, ptitle in p_result.all():
            points_map.setdefault(qid, []).append({"id": pid, "title": ptitle})

    out_items = []
    for q in items:
        item = QuestionOut.model_validate(q)
        item.reviewer_name = reviewer_names.get(q.reviewer_id, "")
        item.points = points_map.get(q.id, [])
        out_items.append(item)

    return QuestionListResponse(total=total, items=out_items)


@router.post("/bank/{question_id}/review")
async def review_question(
    question_id: str,
    req: QuestionReviewRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    _: UserPermissions = Depends(RequirePermission(PERM_QUIZ_MANAGE)),
):
    """审批/编辑/上下架题目"""
    q = await quiz_service.review_question(
        db, question_id, req.action, user.id, req.question, req.reference_answer, req.point_ids
    )
    if not q:
        raise HTTPException(status_code=404, detail="题目不存在或操作无效")
    from sqlalchemy import select
    from app.models.knowledge_unit import QuizQuestionPoint
    from app.models.education import KnowledgePoint

    p_result = await db.execute(
        select(KnowledgePoint.id, KnowledgePoint.title)
        .join(QuizQuestionPoint, QuizQuestionPoint.point_id == KnowledgePoint.id)
        .where(
            QuizQuestionPoint.question_id == question_id,
            KnowledgePoint.status != "rejected",
        )
        .order_by(KnowledgePoint.title)
    )
    out = QuestionOut.model_validate(q)
    out.points = [{"id": pid, "title": ptitle} for pid, ptitle in p_result.all()]
    return out


class RetagRequest(BaseModel):
    question_ids: list[str] = []  # 空 = 全部已发布 + 待审核题


@router.post("/bank/retag")
async def retag_questions(
    req: RetagRequest,
    db: AsyncSession = Depends(get_db),
    _: UserPermissions = Depends(RequirePermission(PERM_QUIZ_MANAGE)),
):
    """按语义重新匹配知识点标签（替换旧标签）"""
    from sqlalchemy import select
    from app.models.knowledge_unit import QuizQuestion, QuizQuestionStatus

    if req.question_ids:
        qids = req.question_ids
    else:
        result = await db.execute(
            select(QuizQuestion.id).where(
                QuizQuestion.status.in_([QuizQuestionStatus.PUBLISHED, QuizQuestionStatus.PENDING_REVIEW])
            )
        )
        qids = list(result.scalars().all())

    tagged = 0
    failed = 0
    for qid in qids:
        try:
            tags = await quiz_service.auto_tag_question(db, qid, replace=True)
            if tags:
                tagged += 1
        except Exception:
            failed += 1
    return {"total": len(qids), "tagged": tagged, "failed": failed}


@router.delete("/bank/{question_id}")
async def delete_question(
    question_id: str,
    db: AsyncSession = Depends(get_db),
    _: UserPermissions = Depends(RequirePermission(PERM_QUIZ_MANAGE)),
):
    """删除题目（与审核共用 quiz:manage 权限）"""
    ok = await quiz_service.delete_question(db, question_id)
    if not ok:
        raise HTTPException(status_code=404, detail="题目不存在")
    return {"deleted": True}


@router.delete("/bank")
async def batch_delete_questions(
    question_ids: list[str] = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
    _: UserPermissions = Depends(RequirePermission(PERM_QUIZ_MANAGE)),
):
    """批量删除题目（与审核共用 quiz:manage 权限）"""
    count = await quiz_service.batch_delete_questions(db, question_ids)
    return {"deleted_count": count}


@router.post("/bank/mine")
async def mine_questions(
    req: MineRequest,
    db: AsyncSession = Depends(get_db),
    _: UserPermissions = Depends(RequirePermission(PERM_QUIZ_MANAGE)),
):
    """从问答日志挖掘用户真实提问作为候选题"""
    stats = await quiz_service.mine_questions_from_qa_logs(db, req.limit)
    return stats


@router.post("/bank/mine-faqs")
async def mine_faq_questions(
    db: AsyncSession = Depends(get_db),
    _: UserPermissions = Depends(RequirePermission(PERM_QUIZ_MANAGE)),
):
    """从问答日志挖掘高频问题并生成参考答案（原 FAQ 挖掘，沉淀入题库）"""
    from app.services.rag import faq_service

    count = await faq_service.mine_faqs(db)
    return {"new_count": count}


@router.post("/bank/sync-cache")
async def sync_pool_cache(
    db: AsyncSession = Depends(get_db),
    _: UserPermissions = Depends(RequirePermission(PERM_QUIZ_MANAGE)),
):
    """全量重建问答缓存（已发布且有参考答案的题库条目）"""
    from app.services.rag import faq_service

    count = await faq_service.sync_faq_cache(db)
    return {"synced_count": count}


@router.get("/bank/duplicates")
async def list_duplicates(
    status: str = Query("pending_review", description="扫描的题目状态"),
    threshold: float = Query(0.92, description="语义相似度阈值"),
    limit: int = Query(200, description="扫描数量上限"),
    db: AsyncSession = Depends(get_db),
    _: UserPermissions = Depends(RequirePermission(PERM_QUIZ_MANAGE)),
):
    """扫描题库中的重复题目，返回重复组列表"""
    groups = await quiz_service.find_duplicates(db, status=status, threshold=threshold, limit=limit)
    return {"groups": groups, "total_groups": len(groups)}


class MergeDuplicatesRequest(BaseModel):
    keep_id: str
    duplicate_ids: list[str]


@router.post("/bank/duplicates/merge")
async def merge_duplicate_questions(
    req: MergeDuplicatesRequest,
    db: AsyncSession = Depends(get_db),
    _: UserPermissions = Depends(RequirePermission(PERM_QUIZ_MANAGE)),
):
    """合并重复题目：保留 keep_id，删除 duplicate_ids，合并使用次数和知识点标签"""
    result = await quiz_service.merge_duplicates(db, req.keep_id, req.duplicate_ids)
    return result


@router.get("/stats/me")
async def my_stats(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """当前用户答题统计"""
    from sqlalchemy import select, func
    from app.models.knowledge_unit import QuizAnswer

    result = await db.execute(
        select(
            func.count(QuizAnswer.id),
            func.avg(QuizAnswer.score),
        ).where(QuizAnswer.user_id == user.id)
    )
    row = result.one()
    count = row[0] or 0
    avg = round(float(row[1]), 1) if row[1] else 0.0

    return {"answer_count": count, "avg_score": avg}
