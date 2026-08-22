"""文档解析节点"""
import os
import logging
from app.graphs.import_graph import ImportState
from app.services.importer.parser_router import parse_file
from app.config import settings

logger = logging.getLogger(__name__)


def node_parse_all(state: ImportState) -> dict:
    split_files = state.get("split_files", [])
    file_path = state["file_path"]
    to_parse = split_files if split_files else [file_path]
    # 优先使用请求参数，否则回退到全局配置
    use_ocr = state.get("use_unlimited_ocr", settings.USE_UNLIMITED_OCR)

    all_text: list[str] = []
    for chunk_path in to_parse:
        chunk_filename = os.path.basename(chunk_path)
        try:
            raw_text = parse_file(chunk_path, chunk_filename, use_unlimited_ocr=use_ocr)
            all_text.append(raw_text)
        except Exception as e:
            logger.warning(f"解析子文件失败: {chunk_filename}, {e}")

    merged_text = "\n\n".join(all_text)
    return {
        "merged_text": merged_text,
        "progress": state.get("needs_split") and 60 or 55,
        "stage": "parsed",
    }