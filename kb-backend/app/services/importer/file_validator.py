import hashlib
import os
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.knowledge_unit import KnowledgeUnit
from app.config import settings

SIZE_LIMITS = {
    "pdf": settings.MAX_SIZE_PDF * 1024 * 1024,
    "docx": settings.MAX_SIZE_DOCX * 1024 * 1024,
    "doc": settings.MAX_SIZE_DOCX * 1024 * 1024,
    "md": settings.MAX_SIZE_MD * 1024 * 1024,
    "txt": settings.MAX_SIZE_TXT * 1024 * 1024,
}

EXT_MAP = {
    ".pdf": "pdf", ".docx": "docx", ".doc": "docx",
    ".md": "md", ".txt": "txt", ".markdown": "md",
}


def compute_md5(file_path: str) -> str:
    """计算文件的 MD5 哈希"""
    h = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def get_file_type(filename: str) -> str:
    """从文件名后缀推断文件类型"""
    _, ext = os.path.splitext(filename)
    return EXT_MAP.get(ext.lower(), "unknown")


def get_file_size_mb(file_path: str) -> float:
    """获取文件大小(MB)"""
    return os.path.getsize(file_path) / (1024 * 1024)


def validate_file_size(file_path: str, file_type: str) -> tuple[bool, str]:
    """
    校验文件大小是否在允许范围内。
    返回 (是否通过, 错误信息)
    """
    limit = SIZE_LIMITS.get(file_type)
    if limit is None:
        return False, f"不支持的文件类型: {file_type}"
    actual = os.path.getsize(file_path)
    if actual > limit:
        limit_mb = limit / (1024 * 1024)
        actual_mb = actual / (1024 * 1024)
        return False, f"文件大小 {actual_mb:.1f}MB 超过 {file_type} 上限 {limit_mb:.0f}MB"
    return True, ""


async def check_duplicate(db: AsyncSession, md5_hash: str) -> KnowledgeUnit | None:
    """按 MD5 查重，返回已存在的知识单元或 None"""
    stmt = select(KnowledgeUnit).where(
        KnowledgeUnit.file_md5 == md5_hash,
        KnowledgeUnit.status != "deleted",
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()