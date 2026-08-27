"""教育体系 API：课程、章节、知识点查询、知识点审核。"""
import json
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import bindparam, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, get_current_user, RequirePermission
from app.core.permissions import UserPermissions, PERM_KNOWLEDGE_MANAGE
from app.models.education import Course, Chapter, KnowledgePoint
from app.models.user import User
from app.schemas.education import CourseOut, ChapterOut, KnowledgePointOut

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/education", tags=["education"])


@router.get("/courses")
async def list_courses(
    db: AsyncSession = Depends(get_db),
):
    """课程列表（仅 active），按 sort_order 排序"""
    stmt = text("SELECT id, title, description, cover_image, status, sort_order, creator_id, created_at, updated_at FROM courses WHERE status = 'active' ORDER BY sort_order, created_at")
    result = await db.execute(stmt)
    rows = result.all()
    return {
        "total": len(rows),
        "items": [
            {
                "id": r[0], "title": r[1], "description": r[2] or "",
                "cover_image": r[3] or "", "status": r[4], "sort_order": r[5],
                "creator_id": r[6] or "",
                "created_at": r[7].isoformat() if r[7] else "",
                "updated_at": r[8].isoformat() if r[8] else "",
            }
            for r in rows
        ],
    }


@router.get("/courses/{course_id}/chapters/tree")
async def get_chapter_tree(
    course_id: str,
    db: AsyncSession = Depends(get_db),
):
    """章节树：递归 CTE 查出某课程下所有章节，Python 侧组装树"""
    stmt = text("""
        WITH RECURSIVE ct AS (
            SELECT id, parent_id, title, sort_order, created_at, updated_at, 0 AS depth
            FROM chapters
            WHERE course_id = :course_id AND parent_id IS NULL
            UNION ALL
            SELECT c.id, c.parent_id, c.title, c.sort_order, c.created_at, c.updated_at, ct.depth + 1
            FROM chapters c
            JOIN ct ON c.parent_id = ct.id
        )
        SELECT id, parent_id, title, sort_order, created_at, updated_at, depth
        FROM ct
        ORDER BY sort_order, depth
    """)
    result = await db.execute(stmt, {"course_id": course_id})
    rows = result.all()

    nodes = {}
    for r in rows:
        nodes[r[0]] = {
            "id": r[0], "parent_id": r[1], "title": r[2],
            "sort_order": r[3],
            "created_at": r[4].isoformat() if r[4] else "",
            "updated_at": r[5].isoformat() if r[5] else "",
            "children": [],
        }

    tree = []
    for r in rows:
        node = nodes[r[0]]
        if r[1] and r[1] in nodes:
            nodes[r[1]]["children"].append(node)
        else:
            tree.append(node)

    return {"tree": tree}


@router.get("/chapters/{chapter_id}/knowledge-points")
async def get_chapter_knowledge_points(
    chapter_id: str,
    db: AsyncSession = Depends(get_db),
):
    """章节下所有知识点（含子孙章节），用于下拉选择"""
    stmt = text("""
        WITH RECURSIVE chapter_tree AS (
            SELECT id FROM chapters WHERE id = :chapter_id
            UNION ALL
            SELECT c.id FROM chapters c
            JOIN chapter_tree ct ON c.parent_id = ct.id
        )
        SELECT DISTINCT kp.id, kp.title, kp.point_type, kp.unit_id
        FROM knowledge_points kp
        JOIN knowledge_units ku ON kp.unit_id = ku.id
        WHERE ku.chapter_id IN (SELECT id FROM chapter_tree)
          AND ku.status != 'deleted'
          AND kp.status NOT IN ('rejected', 'delete_pending')
        ORDER BY kp.title
    """)
    result = await db.execute(stmt, {"chapter_id": chapter_id})
    rows = result.all()
    return {
        "total": len(rows),
        "items": [
            {"id": r[0], "title": r[1], "point_type": r[2], "unit_id": r[3]}
            for r in rows
        ],
    }


# ============================================================================
# 知识点提取与审核
# ============================================================================


@router.get("/units/{unit_id}/points")
async def list_unit_points(
    unit_id: str,
    status: str = "",
    db: AsyncSession = Depends(get_db),
):
    """某知识单元（章节）下的知识点列表，可按状态筛选；附带提取状态"""
    from app.models.knowledge_unit import KnowledgeUnit

    where = "kp.unit_id = :unit_id"
    params = {"unit_id": unit_id}
    if status:
        where += " AND kp.status = :status"
        params["status"] = status
    stmt = text(f"""
        SELECT kp.id, kp.unit_id, kp.title, kp.summary, kp.content, kp.point_type,
               kp.status, kp.candidate_merge_json, kp.source_refs_json, kp.reviewed_at,
               ku.points_status, ku.points_error
        FROM knowledge_points kp
        JOIN knowledge_units ku ON kp.unit_id = ku.id
        WHERE {where}
        ORDER BY kp.created_at, kp.title
    """)
    result = await db.execute(stmt, params)
    rows = result.all()
    if rows:
        return {
            "total": len(rows),
            "points_status": rows[0][10] or "none",
            "points_error": rows[0][11] or "",
            "items": [
                {
                    "id": r[0], "unit_id": r[1], "title": r[2], "summary": r[3],
                    "content": r[4], "point_type": r[5], "status": r[6],
                    "candidate_merges": json.loads(r[7]) if r[7] else [],
                    "source_refs": json.loads(r[8]) if r[8] else [],
                    "reviewed_at": r[9].isoformat() if r[9] else "",
                }
                for r in rows
            ],
        }
    # 无知识点时单独查 unit 状态
    unit = await db.get(KnowledgeUnit, unit_id)
    return {
        "total": 0,
        "points_status": unit.points_status if unit else "none",
        "points_error": unit.points_error if unit else "",
        "items": [],
    }


class BatchPointsRequest(BaseModel):
    unit_ids: list[str] = []


@router.post("/points/batch")
async def batch_unit_points(
    req: BatchPointsRequest,
    db: AsyncSession = Depends(get_db),
):
    """批量查询多个知识单元下的知识点（供章节树展示），排除已拒绝"""
    unit_ids = [u for u in req.unit_ids if u][:300]
    if not unit_ids:
        return {"units": {}}

    stmt = text("""
        SELECT ku.id, ku.points_status, ku.points_error, kp.id, kp.title, kp.status
        FROM knowledge_units ku
        LEFT JOIN knowledge_points kp ON kp.unit_id = ku.id AND kp.status NOT IN ('rejected', 'delete_pending')
        WHERE ku.id IN :unit_ids
        ORDER BY ku.created_at, kp.created_at, kp.title
    """).bindparams(bindparam("unit_ids", expanding=True))
    result = await db.execute(stmt, {"unit_ids": unit_ids})
    rows = result.all()

    units: dict[str, dict] = {}
    for r in rows:
        entry = units.setdefault(r[0], {"points_status": r[1] or "none", "points_error": r[2] or "", "points": []})
        if r[3]:
            entry["points"].append({"id": r[3], "title": r[4], "status": r[5]})
    return {"units": units}


@router.get("/points")
async def list_points(
    status: str = "pending_review",
    offset: int = 0,
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
):
    """知识点审核队列：跨章节按状态列出（pending_review / delete_pending）"""
    if status not in ("pending_review", "delete_pending"):
        raise HTTPException(status_code=400, detail="status 必须是 pending_review 或 delete_pending")
    limit = max(1, min(limit, 50))

    count_result = await db.execute(
        text("SELECT COUNT(*) FROM knowledge_points WHERE status = :status"),
        {"status": status},
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        text("""
            SELECT kp.id, kp.unit_id, ku.title, kp.title, kp.summary, kp.content,
                   kp.status, kp.candidate_merge_json, kp.source_refs_json
            FROM knowledge_points kp
            JOIN knowledge_units ku ON kp.unit_id = ku.id
            WHERE kp.status = :status
            ORDER BY ku.created_at, kp.created_at
            LIMIT :limit OFFSET :offset
        """),
        {"status": status, "limit": limit, "offset": offset},
    )
    rows = result.all()

    # 解析 source_refs，批量补齐来源文档标题
    ref_unit_ids: set[str] = set()
    parsed_refs: dict[str, list] = {}
    for r in rows:
        refs = json.loads(r[8]) if r[8] else []
        if not isinstance(refs, list):
            refs = []
        parsed_refs[r[0]] = refs
        ref_unit_ids.update(x.get("unit_id") for x in refs if isinstance(x, dict) and x.get("unit_id"))

    unit_titles: dict[str, str] = {}
    if ref_unit_ids:
        title_result = await db.execute(
            text("SELECT id, title FROM knowledge_units WHERE id IN :ids")
            .bindparams(bindparam("ids", expanding=True)),
            {"ids": list(ref_unit_ids)},
        )
        unit_titles = {t[0]: t[1] for t in title_result.all()}

    return {
        "total": total,
        "items": [
            {
                "id": r[0], "unit_id": r[1], "unit_title": r[2], "title": r[3],
                "summary": r[4], "content": r[5], "status": r[6],
                "candidate_merges": json.loads(r[7]) if r[7] else [],
                "source_units": [
                    {"unit_id": x.get("unit_id"), "title": unit_titles.get(x.get("unit_id"), "未知文档")}
                    for x in parsed_refs[r[0]] if isinstance(x, dict) and x.get("unit_id")
                ],
            }
            for r in rows
        ],
    }


class PointDeleteReviewRequest(BaseModel):
    action: str  # keep | confirm_delete
    title: str = ""
    content: str = ""


@router.post("/points/{point_id}/delete-review")
async def delete_review_point(
    point_id: str,
    req: PointDeleteReviewRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    _: UserPermissions = Depends(RequirePermission(PERM_KNOWLEDGE_MANAGE)),
):
    """删除待处理知识点的审核：保留（可编辑）/ 确认删除"""
    from app.services.topic_store import delete_topic_vectors_by_point
    from app.services.vectorizer import embed_texts

    point = await db.get(KnowledgePoint, point_id)
    if not point:
        raise HTTPException(status_code=404, detail="知识点不存在")
    if point.status != "delete_pending":
        raise HTTPException(status_code=400, detail="该知识点不在删除待处理状态，请走常规审核")

    if req.action == "keep":
        updates = {"status": "confirmed", "reviewer_id": user.id, "reviewed_at": datetime.now()}
        if req.title.strip():
            updates["title"] = req.title.strip()[:256]
        if req.content.strip():
            updates["content"] = req.content.strip()
            updates["summary"] = req.content.strip()[:200]
        old_title = point.title
        for k, v in updates.items():
            setattr(point, k, v)
        await db.commit()

        new_title = updates.get("title", "")
        if new_title and new_title != old_title:
            try:
                await delete_topic_vectors_by_point(point_id)
                embeddings = await embed_texts([new_title])
                if embeddings:
                    from app.services.topic_store import insert_topic_vectors
                    await insert_topic_vectors([{
                        "point_id": point_id, "title": new_title,
                        "unit_id": point.unit_id, "chapter_id": "", "embedding": embeddings[0],
                    }])
            except Exception as e:
                logger.warning("topic 向量更新失败（不影响审核结果）: point=%s err=%s", point_id, e)
        return {"status": "kept", "point_id": point_id}

    if req.action == "confirm_delete":
        from app.services.importer.knowledge_service import _clean_candidate_merge_refs
        await _clean_candidate_merge_refs(db, point_id)
        await db.delete(point)
        await db.commit()
        await delete_topic_vectors_by_point(point_id)
        return {"status": "deleted", "point_id": point_id}

    raise HTTPException(status_code=400, detail="action 必须是 keep | confirm_delete")


class PointReviewRequest(BaseModel):
    action: str  # confirm | reject | merge
    title: str = ""
    content: str = ""
    merge_into_point_id: str = ""


@router.post("/points/{point_id}/review")
async def review_point(
    point_id: str,
    req: PointReviewRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    _: UserPermissions = Depends(RequirePermission(PERM_KNOWLEDGE_MANAGE)),
):
    """知识点审核：确认 / 拒绝 / 并入已有知识点"""
    from app.services.topic_store import delete_topic_vectors_by_point, insert_topic_vectors
    from app.services.vectorizer import embed_texts

    point = await db.get(KnowledgePoint, point_id)
    if not point:
        raise HTTPException(status_code=404, detail="知识点不存在")
    if point.status == "delete_pending":
        raise HTTPException(status_code=400, detail="该知识点处于删除待处理状态，请走删除审核")

    if req.action == "confirm":
        updates = {"status": "confirmed", "reviewer_id": user.id, "reviewed_at": datetime.now()}
        if req.title.strip():
            updates["title"] = req.title.strip()[:256]
        if req.content.strip():
            updates["content"] = req.content.strip()
            updates["summary"] = req.content.strip()[:200]
        old_title = point.title
        for k, v in updates.items():
            setattr(point, k, v)
        await db.commit()

        # 改名后重嵌入 topic 向量
        new_title = updates.get("title", "")
        if new_title and new_title != old_title:
            try:
                await delete_topic_vectors_by_point(point_id)
                embeddings = await embed_texts([new_title])
                if embeddings:
                    await insert_topic_vectors([{
                        "point_id": point_id, "title": new_title,
                        "unit_id": point.unit_id, "chapter_id": "", "embedding": embeddings[0],
                    }])
            except Exception as e:
                logger.warning("topic 向量更新失败（不影响审核结果）: point=%s err=%s", point_id, e)
        return {"status": "confirmed", "point_id": point_id}

    if req.action == "reject":
        point.status = "rejected"
        point.reviewer_id = user.id
        point.reviewed_at = datetime.now()
        await db.commit()
        await delete_topic_vectors_by_point(point_id)
        return {"status": "rejected", "point_id": point_id}

    if req.action == "merge":
        target = await db.get(KnowledgePoint, req.merge_into_point_id)
        if not target:
            raise HTTPException(status_code=404, detail="并入目标知识点不存在")
        # delta 并入目标：内容拼接，目标回到待审核
        target.content = "\n\n".join(x for x in (target.content.strip(), point.content.strip()) if x)
        target.summary = target.content[:200]
        target.status = "pending_review"
        target.reviewer_id = ""
        target.reviewed_at = None
        await db.delete(point)
        await db.commit()
        await delete_topic_vectors_by_point(point_id)
        return {"status": "merged", "point_id": req.merge_into_point_id}

    raise HTTPException(status_code=400, detail="action 必须是 confirm | reject | merge")


class PointBatchConfirmRequest(BaseModel):
    point_ids: list[str] = []
    all: bool = False


@router.post("/points/batch-confirm")
async def batch_confirm_points(
    req: PointBatchConfirmRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    _: UserPermissions = Depends(RequirePermission(PERM_KNOWLEDGE_MANAGE)),
):
    """批量通过知识点：按 id 列表或 all=true 全部通过。仅作用于待审核状态，其他状态自动跳过"""
    now = datetime.now()
    if req.all:
        result = await db.execute(
            update(KnowledgePoint)
            .where(KnowledgePoint.status == "pending_review")
            .values(status="confirmed", reviewer_id=user.id, reviewed_at=now)
        )
        await db.commit()
        return {"confirmed": result.rowcount, "requested": result.rowcount}
    if not req.point_ids:
        raise HTTPException(status_code=400, detail="point_ids 不能为空")
    for pid in req.point_ids:
        point = await db.get(KnowledgePoint, pid)
        if point and point.status == "pending_review":
            point.status = "confirmed"
            point.reviewer_id = user.id
            point.reviewed_at = now
    await db.commit()
    return {"confirmed": len(req.point_ids), "requested": len(req.point_ids)}


class PointBatchMergeRequest(BaseModel):
    point_ids: list[str]
    target_point_id: str
    new_title: str = ""


@router.post("/points/batch-merge")
async def batch_merge_points(
    req: PointBatchMergeRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    _: UserPermissions = Depends(RequirePermission(PERM_KNOWLEDGE_MANAGE)),
):
    """批量合并知识点（同一文档内）：将多个知识点的内容合并到目标，删除其余"""
    from app.services.topic_store import delete_topic_vectors_by_point, insert_topic_vectors
    from app.services.vectorizer import embed_texts
    from app.services.importer.knowledge_service import _clean_candidate_merge_refs

    if len(req.point_ids) < 2:
        raise HTTPException(status_code=400, detail="至少选择 2 个知识点才能合并")
    if req.target_point_id not in req.point_ids:
        raise HTTPException(status_code=400, detail="目标知识点必须在合并列表中")

    points = []
    for pid in req.point_ids:
        p = await db.get(KnowledgePoint, pid)
        if not p:
            raise HTTPException(status_code=404, detail=f"知识点不存在: {pid}")
        if p.status in ("rejected", "delete_pending"):
            raise HTTPException(status_code=400, detail=f"知识点「{p.title}」状态不允许合并")
        points.append(p)

    unit_ids = {p.unit_id for p in points}
    if len(unit_ids) > 1:
        raise HTTPException(status_code=400, detail="目前仅支持同一文档内的知识点合并")

    target = next(p for p in points if p.id == req.target_point_id)
    others = [p for p in points if p.id != req.target_point_id]

    contents = [target.content.strip()] + [p.content.strip() for p in others]
    target.content = "\n\n".join(x for x in contents if x)
    target.summary = target.content[:200]

    old_title = target.title
    if req.new_title.strip():
        target.title = req.new_title.strip()[:256]

    target.status = "pending_review"
    target.reviewer_id = ""
    target.reviewed_at = None

    deleted_ids = [p.id for p in others]
    for p in others:
        await _clean_candidate_merge_refs(db, p.id)
        await db.delete(p)

    await db.commit()

    for pid in deleted_ids:
        await delete_topic_vectors_by_point(pid)

    new_title = target.title
    if new_title != old_title:
        try:
            await delete_topic_vectors_by_point(target.id)
            embeddings = await embed_texts([new_title])
            if embeddings:
                await insert_topic_vectors([{
                    "point_id": target.id, "title": new_title,
                    "unit_id": target.unit_id, "chapter_id": "", "embedding": embeddings[0],
                }])
        except Exception as e:
            logger.warning("topic 向量更新失败: point=%s err=%s", target.id, e)

    return {"status": "merged", "target_point_id": target.id, "deleted_count": len(deleted_ids)}


@router.post("/units/{unit_id}/extract-points")
async def trigger_extract_points(
    unit_id: str,
    force: bool = False,
    db: AsyncSession = Depends(get_db),
    _: UserPermissions = Depends(RequirePermission(PERM_KNOWLEDGE_MANAGE)),
):
    """手动触发知识点提取（存量文档回填 / 失败重试）"""
    from app.models.knowledge_unit import KnowledgeUnit
    from app.tasks.point_task import extract_points

    unit = await db.get(KnowledgeUnit, unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail="知识单元不存在")
    if unit.status != "published":
        raise HTTPException(status_code=400, detail="文档尚未发布，无法提取")

    task = extract_points.delay(unit_id, force=force)
    return {"task_id": task.id, "unit_id": unit_id, "force": force}
