import json
from datetime import datetime, timedelta
from collections import Counter

from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge_unit import QAAccessLog, KnowledgeUnit, UnitStatus


async def get_metrics(
    db: AsyncSession,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> dict:
    """查询指标卡片数据"""
    if start_date is None:
        start_date = datetime.utcnow() - timedelta(days=30)
    if end_date is None:
        end_date = datetime.utcnow()

    # 访问日志统计
    log_stmt = (
        select(
            func.count(QAAccessLog.id).label("total_visits"),
            func.count(func.distinct(QAAccessLog.user_id)).label("unique_users"),
            func.coalesce(func.sum(QAAccessLog.total_tokens), 0).label("total_tokens"),
            func.coalesce(func.avg(QAAccessLog.response_time_ms), 0).label("avg_response_ms"),
        )
        .where(
            QAAccessLog.created_at >= start_date,
            QAAccessLog.created_at <= end_date,
        )
    )
    result = await db.execute(log_stmt)
    row = result.one()

    # 知识单元数量
    unit_stmt = select(func.count(KnowledgeUnit.id)).where(
        KnowledgeUnit.status != UnitStatus.DELETED,
    )
    unit_result = await db.execute(unit_stmt)
    unit_count = unit_result.scalar() or 0

    return {
        "total_visits": row.total_visits,
        "unique_users": row.unique_users,
        "knowledge_unit_count": unit_count,
        "total_tokens": int(row.total_tokens),
        "avg_response_ms": int(row.avg_response_ms),
    }


async def get_question_rankings(
    db: AsyncSession,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    limit: int = 20,
) -> list[dict]:
    """查询高频问题排行榜"""
    if start_date is None:
        start_date = datetime.utcnow() - timedelta(days=30)
    if end_date is None:
        end_date = datetime.utcnow()

    stmt = (
        select(QAAccessLog.question, func.count(QAAccessLog.id).label("cnt"))
        .where(
            QAAccessLog.created_at >= start_date,
            QAAccessLog.created_at <= end_date,
            func.length(QAAccessLog.question) > 2,
        )
        .group_by(QAAccessLog.question)
        .order_by(func.count(QAAccessLog.id).desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return [{"text": row.question, "count": row.cnt} for row in result.all()]


async def get_unit_rankings(
    db: AsyncSession,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    limit: int = 20,
) -> list[dict]:
    """查询热门知识单元排行榜（基于 recalled_unit_ids_json）"""
    if start_date is None:
        start_date = datetime.utcnow() - timedelta(days=30)
    if end_date is None:
        end_date = datetime.utcnow()

    stmt = select(QAAccessLog.recalled_unit_ids_json).where(
        QAAccessLog.created_at >= start_date,
        QAAccessLog.created_at <= end_date,
    )
    result = await db.execute(stmt)
    rows = result.all()

    # 聚合所有召回记录中的 unit_id
    counter: Counter = Counter()
    for row in rows:
        try:
            ids = json.loads(row.recalled_unit_ids_json)
            if isinstance(ids, list):
                counter.update(ids)
        except (json.JSONDecodeError, TypeError):
            pass

    if not counter:
        return []

    # 根据 unit_id 查询标题
    top_ids = [uid for uid, _ in counter.most_common(limit)]
    unit_stmt = select(KnowledgeUnit.id, KnowledgeUnit.title).where(
        KnowledgeUnit.id.in_(top_ids),
    )
    unit_result = await db.execute(unit_stmt)
    title_map = {row.id: row.title for row in unit_result.all()}

    items = []
    for uid in top_ids:
        items.append({"text": title_map.get(uid, uid), "count": counter[uid]})
    return items


async def get_token_trends(
    db: AsyncSession,
    days: int = 30,
) -> list[dict]:
    """查询 Token 消耗与响应时间趋势（按天聚合）"""
    start_date = datetime.utcnow() - timedelta(days=days)

    stmt = (
        select(
            func.date(QAAccessLog.created_at).label("date"),
            func.coalesce(func.sum(QAAccessLog.total_tokens), 0).label("total_tokens"),
            func.coalesce(func.avg(QAAccessLog.response_time_ms), 0).label("avg_response_ms"),
            func.count(QAAccessLog.id).label("request_count"),
        )
        .where(QAAccessLog.created_at >= start_date)
        .group_by(func.date(QAAccessLog.created_at))
        .order_by(func.date(QAAccessLog.created_at).asc())
    )
    result = await db.execute(stmt)
    return [
        {
            "date": str(row.date),
            "total_tokens": int(row.total_tokens),
            "avg_response_ms": int(row.avg_response_ms),
            "request_count": row.request_count,
        }
        for row in result.all()
    ]