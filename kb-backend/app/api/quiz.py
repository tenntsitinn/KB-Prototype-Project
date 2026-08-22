from fastapi import APIRouter, Depends, HTTPException, Query
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
    """出一道题：题库命中优先，未命中实时生成"""
    result = await quiz_service.next_question(db, user, req.category, req.asked_question_ids)
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
    result = await quiz_service.grade_and_record(db, user, req.question_id, req.answer_text)
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
    category: str = Query(default=""),
    keyword: str = Query(default="", description="题目/参考答案关键词"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: UserPermissions = Depends(RequirePermission(PERM_QUIZ_MANAGE)),
):
    """题库列表（按状态/类别/关键词筛选）"""
    from sqlalchemy import select, func, or_
    from app.models.knowledge_unit import QuizQuestion
    from app.models.user import User

    stmt = select(QuizQuestion)
    if status:
        stmt = stmt.where(QuizQuestion.status == status)
    if category:
        stmt = stmt.where(QuizQuestion.category == category)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(or_(
            QuizQuestion.question.ilike(like),
            QuizQuestion.reference_answer.ilike(like),
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

    out_items = []
    for q in items:
        item = QuestionOut.model_validate(q)
        item.reviewer_name = reviewer_names.get(q.reviewer_id, "")
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
        db, question_id, req.action, user.id, req.question, req.reference_answer
    )
    if not q:
        raise HTTPException(status_code=404, detail="题目不存在或操作无效")
    return QuestionOut.model_validate(q)


@router.post("/bank/mine")
async def mine_questions(
    req: MineRequest,
    db: AsyncSession = Depends(get_db),
    _: UserPermissions = Depends(RequirePermission(PERM_QUIZ_MANAGE)),
):
    """从问答日志挖掘用户真实提问作为候选题"""
    count = await quiz_service.mine_questions_from_qa_logs(db, req.limit)
    return {"new_count": count}


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
