from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, RequirePermission
from app.core.permissions import UserPermissions, PERM_DASHBOARD_VIEW
from app.schemas.dashboard import (
    MetricsResponse,
    RankingsResponse,
    RankingItem,
    TokenTrendsResponse,
    TokenTrendItem,
)
from app.services import dashboard_service

router = APIRouter(prefix="/api/dashboard", tags=["数据看板"])


def _parse_date_range(
    range: str = "month",
) -> tuple[datetime | None, datetime | None]:
    """将时间范围参数转为 start/end 日期"""
    now = datetime.utcnow()
    if range == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return start, now
    if range == "week":
        return now - timedelta(days=7), now
    return now - timedelta(days=30), now


@router.get("/metrics", response_model=MetricsResponse)
async def get_metrics(
    range: str = Query("month", description="today | week | month"),
    db: AsyncSession = Depends(get_db),
    _: UserPermissions = Depends(RequirePermission(PERM_DASHBOARD_VIEW)),
):
    start, end = _parse_date_range(range)
    data = await dashboard_service.get_metrics(db, start, end)
    return MetricsResponse(**data)


@router.get("/rankings/questions", response_model=RankingsResponse)
async def get_question_rankings(
    range: str = Query("month"),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: UserPermissions = Depends(RequirePermission(PERM_DASHBOARD_VIEW)),
):
    start, end = _parse_date_range(range)
    items = await dashboard_service.get_question_rankings(db, start, end, limit)
    return RankingsResponse(items=[RankingItem(**it) for it in items])


@router.get("/rankings/units", response_model=RankingsResponse)
async def get_unit_rankings(
    range: str = Query("month"),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: UserPermissions = Depends(RequirePermission(PERM_DASHBOARD_VIEW)),
):
    start, end = _parse_date_range(range)
    items = await dashboard_service.get_unit_rankings(db, start, end, limit)
    return RankingsResponse(items=[RankingItem(**it) for it in items])


@router.get("/stats/tokens", response_model=TokenTrendsResponse)
async def get_token_trends(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    _: UserPermissions = Depends(RequirePermission(PERM_DASHBOARD_VIEW)),
):
    items = await dashboard_service.get_token_trends(db, days)
    return TokenTrendsResponse(items=[TokenTrendItem(**it) for it in items])