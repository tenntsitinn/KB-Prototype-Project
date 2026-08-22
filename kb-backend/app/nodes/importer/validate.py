"""文件校验节点"""
import os
import logging
from app.graphs.import_graph import ImportState
from app.services.importer.file_validator import compute_md5, validate_file_size, get_file_type

logger = logging.getLogger(__name__)


def node_validate(state: ImportState) -> dict:
    file_path = state["file_path"]
    filename = state["filename"]

    file_type = get_file_type(filename)
    if file_type == "unknown":
        return {"status": "failed", "error": f"不支持的文件格式: {filename}", "progress": 0, "stage": "invalid"}

    valid, err = validate_file_size(file_path, file_type)
    needs_split = file_type in ("pdf", "docx") and not valid

    md5_hash = compute_md5(file_path)
    file_size = int(os.path.getsize(file_path))

    return {
        "file_type": file_type, "file_md5": md5_hash, "file_size": file_size,
        "needs_split": needs_split, "progress": 10, "stage": "validated",
    }


def route_after_validate(state: ImportState) -> str:
    if state.get("status") == "failed":
        return "failed"
    if state.get("needs_split"):
        return "split"
    return "direct"