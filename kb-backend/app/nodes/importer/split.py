"""文档拆分节点（PDF / DOCX）"""
import os
import logging
from app.config import settings
from app.graphs.import_graph import ImportState
from app.services.importer.pdf_splitter import should_split_pdf, split_pdf
from app.services.importer.docx_splitter import should_split_docx, split_docx

logger = logging.getLogger(__name__)


def node_split(state: ImportState) -> dict:
    file_path = state["file_path"]
    file_type = state.get("file_type", "")
    output_dir = os.path.join(settings.UPLOAD_TEMP_DIR, "splits")
    os.makedirs(output_dir, exist_ok=True)

    if file_type == "docx":
        if not should_split_docx(file_path):
            return {"status": "failed", "error": "DOCX 超限但不支持拆分", "stage": "split_failed"}
        chunk_paths = split_docx(file_path, output_dir)
        logger.info("DOCX 拆分完成: %d 个子文件", len(chunk_paths))
    else:
        if not should_split_pdf(file_path):
            return {"status": "failed", "error": "PDF 超限但不支持拆分", "stage": "split_failed"}
        chunk_paths = split_pdf(file_path, output_dir)
        logger.info("PDF 拆分完成: %d 个子文件", len(chunk_paths))

    return {"split_files": chunk_paths, "progress": 15, "stage": "split_done"}