import random

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, get_current_user, RequirePermission
from app.core.permissions import UserPermissions, PERM_AI_ACCESS
from app.models.user import User
from app.models.knowledge_unit import QAAccessLog
from app.schemas.rag import AskRequest, AskResponse, SessionItem, SessionMessage
from app.services.rag.rag_service import rag_service

router = APIRouter(prefix="/api/ai", tags=["RAG"])


@router.post("/chat/stream", response_model=AskResponse)
async def ask(
    req: AskRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    _: UserPermissions = Depends(RequirePermission(PERM_AI_ACCESS)),
):
    """核心问答接口：支持流式和非流式两种模式"""
    result = await rag_service.ask(
        db=db,
        question=req.question,
        user=user,
        session_id=req.session_id,
        stream=req.stream,
        top_k=req.top_k,
    )

    if req.stream:
        return StreamingResponse(
            result,
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    return result


@router.get("/hot-questions")
async def hot_questions(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    _: UserPermissions = Depends(RequirePermission(PERM_AI_ACCESS)),
):
    """热门问题：取最近 100 条问答记录，按提问频次取 top3；
    无高频问题时随机返回 3 条；无记录返回空列表。"""
    stmt = (
        select(QAAccessLog.question)
        .where(QAAccessLog.question != "")
        .order_by(QAAccessLog.created_at.desc())
        .limit(100)
    )
    result = await db.execute(stmt)
    questions = [q.strip() for q in result.scalars().all() if q and q.strip()]

    if not questions:
        return {"questions": []}

    counts: dict[str, int] = {}
    for q in questions:
        counts[q] = counts.get(q, 0) + 1

    top = [q for q, _ in sorted(counts.items(), key=lambda x: (-x[1], x[0]))[:3]]
    if len(counts) > 3 and all(c == 1 for c in counts.values()):
        # 没有重复提问：随机抽 3 条
        top = random.sample(list(counts.keys()), 3)
    return {"questions": top[:3]}


@router.get("/sessions")
async def list_sessions(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """获取当前用户的问答会话列表"""
    subq = (
        select(
            QAAccessLog.session_id,
            func.min(QAAccessLog.created_at).label("first_created"),
            func.max(QAAccessLog.created_at).label("last_created"),
            func.count(QAAccessLog.id).label("msg_count"),
            func.min(QAAccessLog.question).label("first_question"),
        )
        .where(QAAccessLog.user_id == user.id)
        .group_by(QAAccessLog.session_id)
        .subquery()
    )
    stmt = (
        select(subq)
        .order_by(subq.c.last_created.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(stmt)
    rows = result.all()

    total_stmt = select(func.count(func.distinct(QAAccessLog.session_id))).where(
        QAAccessLog.user_id == user.id
    )
    total_result = await db.execute(total_stmt)
    total = total_result.scalar() or 0

    return {
        "total": total,
        "items": [
            SessionItem(
                session_id=row.session_id,
                first_question=(row.first_question or "")[:100],
                message_count=row.msg_count,
                created_at=row.first_created.isoformat() if row.first_created else "",
                updated_at=row.last_created.isoformat() if row.last_created else "",
            )
            for row in rows
        ],
    }


@router.get("/sessions/{session_id}")
async def get_session_messages(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """获取指定会话的问答历史"""
    stmt = (
        select(QAAccessLog)
        .where(
            QAAccessLog.session_id == session_id,
            QAAccessLog.user_id == user.id,
        )
        .order_by(QAAccessLog.created_at.asc())
    )
    result = await db.execute(stmt)
    logs = result.scalars().all()

    if not logs:
        raise HTTPException(status_code=404, detail="会话不存在")

    messages: list[SessionMessage] = []
    for log in logs:
        messages.append(
            SessionMessage(
                role="user",
                content=log.question,
                created_at=log.created_at.isoformat() if log.created_at else "",
            )
        )
        messages.append(
            SessionMessage(
                role="assistant",
                content=log.answer,
                created_at=log.created_at.isoformat() if log.created_at else "",
            )
        )

    return {"session_id": session_id, "messages": messages}