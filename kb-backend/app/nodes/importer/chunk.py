"""文本切片节点"""
import logging
from app.graphs.import_graph import ImportState
from app.services.importer.text_chunker import chunk_text

logger = logging.getLogger(__name__)


def node_chunk(state: ImportState) -> dict:
    chunks = chunk_text(state["merged_text"])
    return {
        "raw_chunks": chunks,
        "chunk_count": len(chunks),
        "progress": state.get("needs_split") and 70 or 65,
        "stage": "chunked",
    }