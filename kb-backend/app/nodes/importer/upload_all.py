"""MinIO 上传节点"""
import os
import logging
from app.config import settings
from app.graphs.import_graph import ImportState
from app.services.importer.minio_client import upload_file, build_object_name

logger = logging.getLogger(__name__)


def node_upload_all(state: ImportState) -> dict:
    file_path = state["file_path"]
    filename = state["filename"]
    unit_id = state["unit_id"]
    split_files = state.get("split_files", [])

    minio_paths: list[str] = []

    orig_object = build_object_name(unit_id, filename)
    upload_file(file_path, settings.MINIO_BUCKET_DOCS, orig_object)
    minio_paths.append(orig_object)

    for i, chunk_path in enumerate(split_files):
        chunk_filename = os.path.basename(chunk_path)
        chunk_object = build_object_name(unit_id, chunk_filename, is_chunk=True, chunk_index=i)
        upload_file(chunk_path, settings.MINIO_BUCKET_DOCS, chunk_object)
        minio_paths.append(chunk_object)

    return {
        "minio_paths": minio_paths,
        "progress": state.get("needs_split") and 35 or 40,
        "stage": "minio_uploaded",
    }