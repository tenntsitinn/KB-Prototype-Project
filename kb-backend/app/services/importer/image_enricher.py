"""
Markdown 图片增强服务：扫描 markdown 中的图片引用 → 视觉模型生成描述 → 上传到 MinIO → 替换为可访问 URL。
"""
import re
import os
import base64
import logging
import mimetypes
from pathlib import Path
from typing import Dict, List, Tuple

from openai import OpenAI

from app.config import settings
from app.services.importer.minio_client import (
    upload_file,
    build_image_object_name,
)

logger = logging.getLogger(__name__)

SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg"}

_vision_client: OpenAI | None = None


def _get_vision_client() -> OpenAI | None:
    """获取视觉模型客户端，未配置则返回 None"""
    global _vision_client
    if not settings.VISION_API_KEY:
        return None
    if _vision_client is None:
        _vision_client = OpenAI(
            api_key=settings.VISION_API_KEY,
            base_url=settings.VISION_BASE_URL,
        )
    return _vision_client


def _find_images_dir(file_path: str) -> Path | None:
    """查找 markdown 文件对应的 images 目录（zip 包场景）"""
    file_dir = Path(file_path).parent
    candidates = [
        file_dir / "images",
        file_dir / "image",
        file_dir / "img",
        file_dir / "assets",
    ]
    for c in candidates:
        if c.exists() and c.is_dir():
            return c
    return None


def _resolve_image_path(ref_path: str, base_dir: Path) -> Path | None:
    """
    解析图片引用路径，支持：
    - 绝对路径（如 Typora 的 C:\\Users\\...\\xxx.png）
    - 相对路径（如 images/xxx.png 或 xxx.png）
    - 回退：仅文件名 → 在 base_dir 及其 images/ 子目录中查找
    """
    path = Path(ref_path)

    # 绝对路径 → 直接检查，存在则返回
    if path.is_absolute():
        if path.exists():
            return path
        # 绝对路径不存在（如 Windows 路径在 Linux 上），回退到文件名搜索
        filename = path.name
        for candidate in [base_dir / filename, base_dir / "images" / filename]:
            if candidate.exists() and candidate.is_file():
                logger.info(f"绝对路径 {ref_path} 不存在，回退到 {candidate}")
                return candidate
        return None

    # 相对路径 → 多个候选目录
    candidates = [
        base_dir / "images" / ref_path,
        base_dir / "image" / ref_path,
        base_dir / "img" / ref_path,
        base_dir / "assets" / ref_path,
        base_dir / ref_path,
    ]
    for c in candidates:
        if c.exists() and c.is_file():
            return c
    return None


def scan_markdown_images(
    md_content: str, base_dir: Path, context_length: int = 200
) -> List[Tuple[str, Path, str, str, str]]:
    """
    扫描 markdown 中所有图片引用，解析为实际文件路径。
    返回: [(图片文件名, 图片完整路径, 原始引用文本, 上文, 下文), ...]
    """
    result = []
    pattern = r"!\[(.*?)\]\(([^)]+)\)"

    for match in re.finditer(pattern, md_content):
        ref_path = match.group(2)
        original_ref = match.group(0)

        resolved = _resolve_image_path(ref_path, base_dir)
        if resolved is None:
            logger.debug(f"图片引用无法解析: {ref_path}")
            continue

        suffix = resolved.suffix.lower()
        if suffix not in SUPPORTED_IMAGE_EXTENSIONS:
            continue

        start, end = match.span()
        pre_context = md_content[max(start - context_length, 0) : start]
        post_context = md_content[end : min(end + context_length, len(md_content))]
        result.append((resolved.name, resolved, original_ref, pre_context, post_context))

    logger.info(f"扫描到 {len(result)} 张可解析的图片引用")
    return result


def _describe_image(image_path: Path, pre_context: str, post_context: str) -> str:
    """调用视觉模型生成图片描述，未配置则返回空字符串"""
    client = _get_vision_client()
    if client is None:
        return ""

    image_bytes = image_path.read_bytes()
    image_base64 = base64.b64encode(image_bytes).decode("utf-8")
    mime_type, _ = mimetypes.guess_type(str(image_path))
    mime_type = mime_type or "image/png"

    prompt = (
        "请用一句简短的中文描述这张图片的内容，用于替代 markdown 中的图片 alt 文本。\n"
        f"图片上下文——上文：{pre_context[:200]}\n下文：{post_context[:200]}\n"
        "请只输出描述文本，不要加任何前缀或解释。"
    )

    try:
        response = client.chat.completions.create(
            model=settings.VISION_MODEL,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{image_base64}"}},
                    {"type": "text", "text": prompt},
                ],
            }],
            max_tokens=100,
            temperature=0.3,
        )
        desc = response.choices[0].message.content.strip()
        logger.info(f"图片 {image_path.name} 视觉描述: {desc}")
        return desc
    except Exception as e:
        logger.warning(f"视觉模型调用失败: {e}")
        return ""


def _describe_images_batch(
    image_refs: List[Tuple[str, Path, str, str, str]],
) -> Dict[str, str]:
    """批量生成图片描述，返回 {图片名: 描述}"""
    result: Dict[str, str] = {}
    for image_name, image_path, _ref, pre_ctx, post_ctx in image_refs:
        desc = _describe_image(image_path, pre_ctx, post_ctx)
        result[image_name] = desc
    return result


def upload_images_and_replace(
    image_refs: List[Tuple[str, Path, str, str, str]],
    image_descriptions: Dict[str, str],
    md_content: str,
    unit_id: str,
) -> str:
    """
    上传图片到 MinIO，替换 markdown 中的本地路径为后端代理 URL。
    使用视觉模型生成的描述作为 alt 文本。
    """
    bucket = settings.MINIO_BUCKET_DOCS

    for image_name, image_path, original_ref, _pre, _post in image_refs:
        try:
            object_name = build_image_object_name(unit_id, image_name)
            upload_file(str(image_path), bucket, object_name)

            proxy_url = f"/api/knowledge/images/{unit_id}/{image_name}"
            alt_text = image_descriptions.get(image_name) or image_name
            new_ref = f"![{alt_text}]({proxy_url})"

            md_content = md_content.replace(original_ref, new_ref)
            logger.info(f"图片 {image_name} 已上传并替换 → {proxy_url}")
        except Exception as e:
            logger.warning(f"图片 {image_name} 上传失败: {e}")

    return md_content


def enrich_markdown_images(md_content: str, file_path: str, unit_id: str) -> str:
    """
    Markdown 图片增强入口：扫描所有图片引用 → 视觉描述 → 上传 → 替换。
    支持绝对路径（Typora）、相对路径（zip 包 images/）、仅文件名。
    无法解析的图片引用会被移除，避免残留本地路径。
    """
    base_dir = Path(file_path).parent
    image_refs = scan_markdown_images(md_content, base_dir)

    if image_refs:
        image_descriptions = _describe_images_batch(image_refs)
        md_content = upload_images_and_replace(image_refs, image_descriptions, md_content, unit_id)

    # 清理残留的本地/绝对路径图片引用（无法解析的）
    cleaned = re.sub(r"!\[[^\]]*\]\([A-Za-z]:\\[^)]+\)", "", md_content)
    if cleaned != md_content:
        logger.info("已清除无法解析的本地图片引用")
        md_content = cleaned

    return md_content