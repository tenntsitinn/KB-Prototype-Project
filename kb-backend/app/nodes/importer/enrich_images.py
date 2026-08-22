"""Markdown 图片增强节点：在解析后、切片前，替换本地图片路径为 MinIO URL"""
import re
import logging
from app.graphs.import_graph import ImportState
from app.services.importer.image_enricher import enrich_markdown_images

logger = logging.getLogger(__name__)


def node_enrich_images(state: ImportState) -> dict:
    """扫描 markdown 中的图片引用，上传到 MinIO 并替换为可访问 URL"""
    merged_text = state.get("merged_text", "")
    file_path = state["file_path"]
    file_type = state.get("file_type", "")
    unit_id = state["unit_id"]

    if file_type not in ("md", "pdf"):
        logger.debug(f"文件类型为 {file_type}，跳过图片增强")
        return {}

    if not merged_text:
        return {}

    enriched = enrich_markdown_images(merged_text, file_path, unit_id)

    if enriched != merged_text:
        logger.info("markdown 图片已增强，替换为 MinIO URL")
        # 图片用双换行包裹，确保 chunker 为每张图创建独立 chunk
        enriched = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", r"\n\n![\1](\2)\n\n", enriched)
        enriched = re.sub(r"\n{3,}", "\n\n", enriched)
        return {"merged_text": enriched, "stage": "images_enriched"}
    else:
        return {}