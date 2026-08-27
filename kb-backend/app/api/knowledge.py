import os
import shutil
import zipfile
import tempfile
from typing import List
from urllib.parse import quote
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Form, Query, Body
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
import hmac
import hashlib
import time

from app.config import settings
from app.core.dependencies import get_db, get_current_user, get_current_permissions, get_current_permissions_optional, RequirePermission
from app.core.permissions import (
    UserPermissions, PERM_KNOWLEDGE_MANAGE,
    PERM_KNOWLEDGE_MANAGE_PERMISSIONS,
)
from app.models.user import User
from app.models.knowledge_unit import KnowledgeUnit
from app.schemas.knowledge import (
    KnowledgeUnitUpdate,
    PermissionBatchCreate,
    PermissionOut,
    CheckPermissionsRequest,
    CheckPermissionsResponse,
    ImportResponse,
    ImportItem,
    BatchImportResponse,
    ImportStatusResponse,
)
from app.services.importer.file_validator import compute_md5, get_file_type, validate_file_size, check_duplicate
from app.services.importer.knowledge_service import (
    get_knowledge_unit,
    list_knowledge_units,
    update_knowledge_unit,
    get_unit_permissions,
    set_unit_permissions,
    check_unit_permissions,
    batch_soft_delete_knowledge_units,
    soft_delete_knowledge_unit,
    restore_knowledge_unit,
    permanent_delete_knowledge_unit,
)

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


def _extract_zip(tmp_path: str) -> tuple[str, str]:
    """
    解压 zip 包，寻找其中的 .md 文件。
    返回 (md_file_path, extract_dir) — extract_dir 用于后续清理。
    """
    extract_dir = tempfile.mkdtemp(prefix="kb_zip_", dir=settings.UPLOAD_TEMP_DIR)
    with zipfile.ZipFile(tmp_path, "r") as zf:
        zf.extractall(extract_dir)

    md_files = []
    for root, _dirs, files in os.walk(extract_dir):
        for f in files:
            if f.lower().endswith((".md", ".markdown")):
                md_files.append(os.path.join(root, f))

    if not md_files:
        raise HTTPException(status_code=400, detail="zip 包中未找到 .md 文件")

    md_path = md_files[0]
    if len(md_files) > 1:
        # 优先选择与 zip 同名的 .md
        stem = os.path.splitext(os.path.basename(tmp_path))[0]
        for p in md_files:
            if os.path.splitext(os.path.basename(p))[0] == stem:
                md_path = p
                break

    return md_path, extract_dir


async def _process_single_file(tmp_path: str, filename: str, creator_id: str, db: AsyncSession) -> ImportItem:
    """处理单个文件：校验 + 查重 + 投递 Celery 任务，返回 ImportItem"""
    is_zip = filename.lower().endswith(".zip")

    if is_zip:
        try:
            md_path, _extract_dir = _extract_zip(tmp_path)
        except Exception as e:
            return ImportItem(
                filename=filename, task_id="", unit_id="", status="failed",
                error=f"zip 解压失败: {e}",
            )
        os.remove(tmp_path)
        tmp_path = md_path
        filename = os.path.basename(md_path)

    file_type = get_file_type(filename)
    if file_type == "unknown":
        return ImportItem(
            filename=filename, task_id="", unit_id="", status="failed",
            error=f"不支持的文件格式: {filename}",
        )

    valid, err = validate_file_size(tmp_path, file_type)
    if not valid and file_type not in ("pdf", "docx"):
        os.remove(tmp_path)
        return ImportItem(
            filename=filename, task_id="", unit_id="", status="failed", error=err,
        )

    md5_hash = compute_md5(tmp_path)
    existing = await check_duplicate(db, md5_hash)
    if existing:
        return ImportItem(
            filename=filename, task_id="", unit_id=existing.id, status="duplicate",
            error=f"文件已存在（MD5: {md5_hash[:8]}...）",
        )

    from app.tasks.import_task import process_document
    task = process_document.delay(tmp_path, filename, creator_id)
    return ImportItem(
        filename=filename, task_id=task.id, unit_id="pending", status="pending",
    )


# ---------------------------------------------------------------------------
# 文档导入
# ---------------------------------------------------------------------------

@router.post("/import", response_model=ImportResponse)
async def import_document(
    file: UploadFile = File(...),
    creator_id: str = Form(default="system"),
    category: str = Form(default=""),
    use_unlimited_ocr: bool = Form(default=False),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    _: UserPermissions = Depends(RequirePermission(PERM_KNOWLEDGE_MANAGE)),
):
    """单文件导入接口，支持 .md / .pdf / .docx / .txt / .zip"""
    filename = file.filename or "unknown"
    file_type = get_file_type(filename)
    is_zip = filename.lower().endswith(".zip")

    if file_type == "unknown" and not is_zip:
        raise HTTPException(status_code=400, detail=f"不支持的文件格式: {filename}")

    category = category.strip()
    if len(category) > 50:
        raise HTTPException(status_code=400, detail="分类名过长（最多 50 字符）")

    # 上传者输入的新标签值自动入库，标签表随上传自然增长
    if category:
        from app.services import tag_service
        await tag_service.ensure_tag(db, category)

    os.makedirs(settings.UPLOAD_TEMP_DIR, exist_ok=True)
    tmp_path = os.path.join(settings.UPLOAD_TEMP_DIR, filename)
    with open(tmp_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # zip 包处理：解压找 .md，图片目录保留在解压目录中
    if is_zip:
        try:
            md_path, extract_dir = _extract_zip(tmp_path)
        except HTTPException:
            raise
        except Exception as e:
            os.remove(tmp_path)
            raise HTTPException(status_code=400, detail=f"zip 解压失败: {e}")
        os.remove(tmp_path)
        tmp_path = md_path
        filename = os.path.basename(md_path)
        file_type = "md"

    valid, err = validate_file_size(tmp_path, file_type)
    if not valid and file_type not in ("pdf", "docx"):
        os.remove(tmp_path)
        raise HTTPException(status_code=400, detail=err)

    md5_hash = compute_md5(tmp_path)
    existing = await check_duplicate(db, md5_hash)
    if existing:
        raise HTTPException(status_code=409, detail=f"文件已存在（MD5: {md5_hash[:8]}...）")

    from app.tasks.import_task import process_document
    task = process_document.delay(tmp_path, filename, creator_id, category=category, use_unlimited_ocr=use_unlimited_ocr)

    return ImportResponse(
        task_id=task.id,
        unit_id="pending",
        status="pending",
    )


@router.post("/import/batch", response_model=BatchImportResponse)
async def batch_import_documents(
    files: List[UploadFile] = File(...),
    creator_id: str = Form(default="system"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    _: UserPermissions = Depends(RequirePermission(PERM_KNOWLEDGE_MANAGE)),
):
    """批量文件导入接口：支持多文件并发上传，返回每个文件的导入结果"""
    os.makedirs(settings.UPLOAD_TEMP_DIR, exist_ok=True)
    items: list[ImportItem] = []

    for file in files:
        filename = file.filename or "unknown"
        tmp_path = os.path.join(settings.UPLOAD_TEMP_DIR, filename)
        try:
            with open(tmp_path, "wb") as f:
                shutil.copyfileobj(file.file, f)
        except Exception as e:
            items.append(ImportItem(
                filename=filename, task_id="", unit_id="", status="failed", error=str(e),
            ))
            continue

        items.append(await _process_single_file(tmp_path, filename, creator_id, db))

    return BatchImportResponse(total=len(items), items=items)


@router.get("/import/{task_id}/status", response_model=ImportStatusResponse)
async def get_import_status(task_id: str):
    """查询异步导入任务进度"""
    from celery.result import AsyncResult
    result = AsyncResult(task_id)
    meta = result.info if result.info else {}

    return ImportStatusResponse(
        task_id=task_id,
        unit_id=meta.get("unit_id", ""),
        status=result.status.lower(),
        progress=meta.get("progress", 0),
        error=meta.get("error", ""),
    )


# ---------------------------------------------------------------------------
# 大文件分片上传
# ---------------------------------------------------------------------------

CHUNK_SIZE = 5 * 1024 * 1024  # 5MB per chunk
CHUNK_THRESHOLD = 10 * 1024 * 1024  # 文件 > 10MB 时使用分片上传


def _chunk_dir(upload_id: str) -> str:
    """安全构造分片存储目录，防止路径遍历"""
    safe_id = upload_id.replace("/", "").replace("\\", "").replace("..", "")
    return os.path.join(settings.UPLOAD_TEMP_DIR, "chunks", safe_id)


@router.post("/upload/chunk")
async def upload_chunk(
    upload_id: str = Form(...),
    chunk_index: int = Form(...),
    total_chunks: int = Form(...),
    chunk: UploadFile = File(...),
    user: User = Depends(get_current_user),
    _: UserPermissions = Depends(RequirePermission(PERM_KNOWLEDGE_MANAGE)),
):
    """上传单个分片"""
    chunk_dir = _chunk_dir(upload_id)
    os.makedirs(chunk_dir, exist_ok=True)

    chunk_path = os.path.join(chunk_dir, f"chunk_{chunk_index:05d}")
    with open(chunk_path, "wb") as f:
        shutil.copyfileobj(chunk.file, f)

    uploaded = len(os.listdir(chunk_dir))
    return {
        "upload_id": upload_id,
        "chunk_index": chunk_index,
        "uploaded": uploaded,
        "total_chunks": total_chunks,
    }


@router.get("/upload/chunks")
async def check_uploaded_chunks(
    upload_id: str = Query(...),
    user: User = Depends(get_current_user),
    _: UserPermissions = Depends(RequirePermission(PERM_KNOWLEDGE_MANAGE)),
):
    """查询已上传的分片索引列表（用于断点续传）"""
    chunk_dir = _chunk_dir(upload_id)
    if not os.path.exists(chunk_dir):
        return {"upload_id": upload_id, "uploaded": []}

    indices = []
    for name in os.listdir(chunk_dir):
        if name.startswith("chunk_"):
            try:
                indices.append(int(name[6:]))
            except ValueError:
                pass
    return {"upload_id": upload_id, "uploaded": sorted(indices)}


@router.post("/upload/merge", response_model=ImportResponse)
async def merge_chunks(
    upload_id: str = Form(...),
    filename: str = Form(...),
    total_chunks: int = Form(...),
    creator_id: str = Form(default="system"),
    category: str = Form(default=""),
    use_unlimited_ocr: bool = Form(default=False),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    _: UserPermissions = Depends(RequirePermission(PERM_KNOWLEDGE_MANAGE)),
):
    """合并所有分片为完整文件，然后走正常导入流程"""
    chunk_dir = _chunk_dir(upload_id)
    if not os.path.exists(chunk_dir):
        raise HTTPException(status_code=404, detail="上传会话不存在或已过期")

    existing_chunks = len(os.listdir(chunk_dir))
    if existing_chunks != total_chunks:
        raise HTTPException(
            status_code=400,
            detail=f"分片不完整: {existing_chunks}/{total_chunks}",
        )

    file_type = get_file_type(filename)
    if file_type == "unknown":
        shutil.rmtree(chunk_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail=f"不支持的文件格式: {filename}")

    category = category.strip()
    if len(category) > 50:
        shutil.rmtree(chunk_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail="分类名过长（最多 50 字符）")

    if category:
        from app.services import tag_service
        await tag_service.ensure_tag(db, category)

    os.makedirs(settings.UPLOAD_TEMP_DIR, exist_ok=True)
    merged_path = os.path.join(settings.UPLOAD_TEMP_DIR, filename)
    try:
        with open(merged_path, "wb") as f:
            for i in range(total_chunks):
                chunk_path = os.path.join(chunk_dir, f"chunk_{i:05d}")
                if not os.path.exists(chunk_path):
                    raise HTTPException(
                        status_code=400,
                        detail=f"分片 {i} 缺失",
                    )
                with open(chunk_path, "rb") as chunk_file:
                    shutil.copyfileobj(chunk_file, f)
    finally:
        shutil.rmtree(chunk_dir, ignore_errors=True)

    valid, err = validate_file_size(merged_path, file_type)
    if not valid and file_type not in ("pdf", "docx"):
        os.remove(merged_path)
        raise HTTPException(status_code=400, detail=err)

    md5_hash = compute_md5(merged_path)
    existing = await check_duplicate(db, md5_hash)
    if existing:
        os.remove(merged_path)
        raise HTTPException(status_code=409, detail=f"文件已存在（MD5: {md5_hash[:8]}...）")

    from app.tasks.import_task import process_document
    task = process_document.delay(
        merged_path, filename, creator_id,
        category=category, use_unlimited_ocr=use_unlimited_ocr,
    )

    return ImportResponse(
        task_id=task.id,
        unit_id="pending",
        status="pending",
    )


# ---------------------------------------------------------------------------
# 知识单元 CRUD
# ---------------------------------------------------------------------------

@router.get("/units")
async def list_units(
    title: str | None = None,
    category: str | None = None,
    status: str | None = None,
    course_id: str | None = None,
    chapter_id: str | None = None,
    offset: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """分页查询知识单元列表"""
    units, total = await list_knowledge_units(db, title, category, status, offset, limit, course_id, chapter_id)
    return {
        "total": total,
        "items": [
            {
                "id": u.id,
                "unit_code": u.unit_code,
                "title": u.title,
                "category": u.category,
                "file_type": u.file_type,
                "file_size": u.file_size,
                "status": u.status,
                "source_file_name": u.source_file_name,
                "creator_id": u.creator_id,
                "deleted_at": u.deleted_at.isoformat() if u.deleted_at else None,
                "created_at": u.created_at.isoformat(),
                "updated_at": u.updated_at.isoformat(),
            }
            for u in units
        ],
    }


@router.get("/units/{unit_id}")
async def get_unit(
    unit_id: str,
    db: AsyncSession = Depends(get_db),
):
    """查询知识单元详情（含数据权限列表）"""
    unit = await get_knowledge_unit(db, unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail="知识单元不存在")

    permissions = await get_unit_permissions(db, unit_id)

    return {
        "id": unit.id,
        "unit_code": unit.unit_code,
        "title": unit.title,
        "content": unit.content,
        "summary": unit.summary,
        "category": unit.category,
        "source_file_name": unit.source_file_name,
        "file_type": unit.file_type,
        "file_size": unit.file_size,
        "status": unit.status,
        "creator_id": unit.creator_id,
        "created_at": unit.created_at.isoformat(),
        "updated_at": unit.updated_at.isoformat(),
        "permissions": [
            {"id": p.id, "unit_id": p.unit_id, "target_type": p.target_type, "target_id": p.target_id}
            for p in permissions
        ],
    }


# ---------------------------------------------------------------------------
# 原文档短时签名访问：浏览器原生预览 PDF/MD/TXT，避免弹窗拦截与全量内存下载
# ---------------------------------------------------------------------------

_FILE_TOKEN_TTL = 300  # 签名有效期（秒）
_PRESIGN_TTL = 600  # 预签名 URL 有效期（秒）


def _sign_unit_file(unit_id: str, expires: int) -> str:
    msg = f"{unit_id}:{expires}".encode()
    return hmac.new(settings.JWT_SECRET_KEY.encode(), msg, hashlib.sha256).hexdigest()


def _verify_unit_file_token(unit_id: str, st: str) -> bool:
    try:
        expires_str, sig = st.split(".", 1)
        expires = int(expires_str)
        if time.time() > expires:
            return False
        return hmac.compare_digest(sig, _sign_unit_file(unit_id, expires))
    except Exception:
        return False


@router.get("/units/{unit_id}/file-url")
async def get_unit_file_url(
    unit_id: str,
    db: AsyncSession = Depends(get_db),
):
    """签发原文档的短时访问 URL（预签名直连 MinIO，10 分钟有效）"""
    import mimetypes
    from app.services.importer.minio_client import get_presigned_url

    unit = await get_knowledge_unit(db, unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail="知识单元不存在")
    if not unit.minio_path:
        raise HTTPException(status_code=404, detail="原始文档不存在")

    filename = unit.source_file_name or os.path.basename(unit.minio_path)
    mime_type, _ = mimetypes.guess_type(filename)
    media_type = mime_type or "application/octet-stream"
    inline_types = {"application/pdf", "text/markdown", "text/plain"}
    disposition = "inline" if media_type in inline_types else "attachment"

    url = get_presigned_url(
        settings.MINIO_BUCKET_DOCS,
        unit.minio_path,
        expires_seconds=_PRESIGN_TTL,
        content_disposition=f"{disposition}; filename*=UTF-8''{quote(filename)}",
        content_type=media_type,
    )
    return {"url": url, "expires_in": _PRESIGN_TTL}


@router.get("/units/{unit_id}/file")
async def get_unit_file(
    unit_id: str,
    st: str = Query(default=""),
    db: AsyncSession = Depends(get_db),
    perms: UserPermissions | None = Depends(get_current_permissions_optional),
):
    """下载/预览知识单元的原始文档。

    两种访问方式：带 Authorization 头走正常鉴权（所有登录用户可访问）；
    或带有效签名参数 st（由 file-url 接口签发，5 分钟内有效）。
    """
    if st:
        if not _verify_unit_file_token(unit_id, st):
            raise HTTPException(status_code=401, detail="签名无效或已过期")
    else:
        if perms is None:
            raise HTTPException(status_code=403, detail="权限不足")

    import mimetypes
    from app.services.importer.minio_client import download_file

    unit = await get_knowledge_unit(db, unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail="知识单元不存在")
    if not unit.minio_path:
        raise HTTPException(status_code=404, detail="原始文档不存在")

    filename = unit.source_file_name or os.path.basename(unit.minio_path)
    tmp_path = os.path.join(tempfile.gettempdir(), f"kb_file_{unit_id}_{filename}")
    try:
        download_file(settings.MINIO_BUCKET_DOCS, unit.minio_path, tmp_path)
    except Exception:
        raise HTTPException(status_code=404, detail="原始文档不存在")

    mime_type, _ = mimetypes.guess_type(filename)
    media_type = mime_type or "application/octet-stream"
    inline_types = {"application/pdf", "text/markdown", "text/plain"}
    disposition = "inline" if media_type in inline_types else "attachment"

    def iterfile():
        with open(tmp_path, "rb") as f:
            yield from f
        os.remove(tmp_path)

    return StreamingResponse(
        iterfile(),
        media_type=media_type,
        headers={"Content-Disposition": f"{disposition}; filename*=UTF-8''{quote(filename)}"},
    )


@router.put("/units/{unit_id}")
async def update_unit(
    unit_id: str,
    data: KnowledgeUnitUpdate,
    db: AsyncSession = Depends(get_db),
    _: UserPermissions = Depends(RequirePermission(PERM_KNOWLEDGE_MANAGE)),
):
    """更新知识单元内容（需知识写入权限）"""

    # 编辑时输入的新标签值自动入库
    if data.category is not None:
        from app.services import tag_service
        await tag_service.ensure_tag(db, data.category)

    unit = await update_knowledge_unit(db, unit_id, data)
    if not unit:
        raise HTTPException(status_code=404, detail="知识单元不存在或已删除")

    return {
        "id": unit.id,
        "unit_code": unit.unit_code,
        "title": unit.title,
        "content": unit.content,
        "summary": unit.summary,
        "category": unit.category,
        "file_type": unit.file_type,
        "status": unit.status,
        "updated_at": unit.updated_at.isoformat(),
    }


@router.post("/units/{unit_id}/retry-vectorize", response_model=ImportResponse)
async def retry_vectorize(
    unit_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    _: UserPermissions = Depends(RequirePermission(PERM_KNOWLEDGE_MANAGE)),
):
    """断点续跑：对向量化失败（草稿状态）的单元重新向量化，已成功的 chunk 不重做"""
    unit = await db.get(KnowledgeUnit, unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail="知识单元不存在")
    if unit.status == "published":
        raise HTTPException(status_code=400, detail="该单元已发布，无需重试")
    if unit.status == "deleted":
        raise HTTPException(status_code=400, detail="该单元已删除，请先恢复")

    from app.tasks.import_task import retry_vectorize as retry_task
    task = retry_task.delay(unit_id)
    return ImportResponse(task_id=task.id, unit_id=unit_id, status="pending")


@router.put("/units/batch/restore")
async def batch_restore_units(
    unit_ids: List[str] = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
    _: UserPermissions = Depends(RequirePermission(PERM_KNOWLEDGE_MANAGE)),
):
    """批量恢复已删除的知识单元（需知识管理权限）"""
    from app.services.importer.knowledge_service import batch_restore_knowledge_units
    restored = await batch_restore_knowledge_units(db, unit_ids)
    return {"restored_count": restored}


@router.delete("/units/batch/permanent")
async def batch_permanent_delete_units(
    unit_ids: List[str] = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
    _: UserPermissions = Depends(RequirePermission(PERM_KNOWLEDGE_MANAGE)),
):
    """批量永久删除知识单元（需知识管理权限）"""
    from app.services.importer.knowledge_service import batch_permanent_delete_knowledge_units
    deleted = await batch_permanent_delete_knowledge_units(db, unit_ids)
    return {"deleted_count": deleted}


@router.delete("/units/{unit_id}")
async def delete_unit(
    unit_id: str,
    db: AsyncSession = Depends(get_db),
    _: UserPermissions = Depends(RequirePermission(PERM_KNOWLEDGE_MANAGE)),
):
    """软删除知识单元（需知识删除权限）"""

    deleted = await soft_delete_knowledge_unit(db, unit_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="知识单元不存在")
    return {"deleted": True}


@router.delete("/units")
async def batch_delete_units(
    unit_ids: List[str] = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
    _: UserPermissions = Depends(RequirePermission(PERM_KNOWLEDGE_MANAGE)),
):
    """批量软删除知识单元（需知识删除权限）"""

    deleted_count = await batch_soft_delete_knowledge_units(db, unit_ids)
    return {"deleted_count": deleted_count}


@router.put("/units/{unit_id}/restore")
async def restore_unit(
    unit_id: str,
    db: AsyncSession = Depends(get_db),
    _: UserPermissions = Depends(RequirePermission(PERM_KNOWLEDGE_MANAGE)),
):
    """恢复已删除的知识单元（需知识删除权限）"""

    restored = await restore_knowledge_unit(db, unit_id)
    if not restored:
        raise HTTPException(status_code=404, detail="知识单元不存在或未被删除")
    return {"restored": True}


@router.delete("/units/{unit_id}/permanent")
async def permanent_delete_unit(
    unit_id: str,
    db: AsyncSession = Depends(get_db),
    _: UserPermissions = Depends(RequirePermission(PERM_KNOWLEDGE_MANAGE)),
):
    """永久删除知识单元（需知识删除权限）"""

    deleted = await permanent_delete_knowledge_unit(db, unit_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="知识单元不存在")
    return {"deleted": True}


# ---------------------------------------------------------------------------
# 数据权限
# ---------------------------------------------------------------------------

@router.post("/units/{unit_id}/permissions")
async def configure_unit_permissions(
    unit_id: str,
    data: PermissionBatchCreate,
    db: AsyncSession = Depends(get_db),
    _: UserPermissions = Depends(RequirePermission(PERM_KNOWLEDGE_MANAGE_PERMISSIONS)),
):
    """批量配置知识单元的数据权限（需数据权限管理权限）"""

    unit = await get_knowledge_unit(db, unit_id)
    if not unit:
        raise HTTPException(status_code=404, detail="知识单元不存在")

    perms = await set_unit_permissions(db, unit_id, data.permissions)
    return {
        "unit_id": unit_id,
        "permissions": [
            {"id": p.id, "unit_id": p.unit_id, "target_type": p.target_type, "target_id": p.target_id}
            for p in perms
        ],
    }


@router.post("/check-permissions", response_model=CheckPermissionsResponse)
async def check_permissions(
    data: CheckPermissionsRequest,
    db: AsyncSession = Depends(get_db),
    _permissions: UserPermissions = Depends(get_current_permissions),
):
    """权限鉴权审查：传入 user_id 和 unit_ids，返回有权限和无权限的列表"""
    authorized, unauthorized = await check_unit_permissions(db, data.user_id, data.unit_ids)
    return CheckPermissionsResponse(
        authorized_unit_ids=authorized,
        unauthorized_unit_ids=unauthorized,
    )


# ---------------------------------------------------------------------------
# 图片代理
# ---------------------------------------------------------------------------

@router.get("/images/{unit_id}/{image_name}")
async def serve_image(unit_id: str, image_name: str):
    """代理 MinIO 中的图片，供前端 markdown 渲染使用"""
    import mimetypes
    from app.services.importer.minio_client import download_file, build_image_object_name

    object_name = build_image_object_name(unit_id, image_name)
    bucket = settings.MINIO_BUCKET_DOCS

    tmp_path = os.path.join(tempfile.gettempdir(), f"kb_img_{unit_id}_{image_name}")
    try:
        download_file(bucket, object_name, tmp_path)
    except Exception:
        raise HTTPException(status_code=404, detail="图片不存在")

    mime_type, _ = mimetypes.guess_type(image_name)
    media_type = mime_type or "application/octet-stream"

    def iterfile():
        with open(tmp_path, "rb") as f:
            yield from f
        os.remove(tmp_path)

    return StreamingResponse(iterfile(), media_type=media_type)