"""
文档导入管道 LangGraph 状态图。

图结构:
  START → validate → [超限PDF] → split → create_unit → upload_all → parse_all → enrich_images → chunk → vectorize → update → END
                    → [正常]    ───────────────────────────────────────────────────────────────────────────────────────┘

本文件包含：状态类型定义、图构建。
节点函数在 app/nodes/import/。
"""
import logging
from typing import TypedDict

from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph

from app.services.importer.text_chunker import Chunk

logger = logging.getLogger(__name__)


# ============================================================================
# 图状态
# ============================================================================


class ImportState(TypedDict, total=False):
    """导入管道状态，在节点间传递"""

    # ── 输入 ──
    file_path: str       # 原始文件路径
    filename: str        # 原始文件名
    creator_id: str      # 上传用户 ID
    category: str        # 上传者选定的标签名
    use_unlimited_ocr: bool  # 是否使用 Unlimited-OCR（默认 MinerU）

    # ── 中间结果 ──
    file_type: str       # txt | md | docx | pdf | unknown
    file_md5: str        # 原始文件 MD5
    file_size: int       # 原始文件大小 (bytes)
    needs_split: bool    # 是否需要拆分 PDF
    split_files: list[str]  # 待处理文件列表（正常: [file_path]; 拆分: [chunk1, chunk2, ...])
    unit_id: str
    unit_code: str
    minio_paths: list[str]  # MinIO 对象名列表
    merged_text: str     # 合并后的全文
    raw_chunks: list[Chunk]  # 切片结果
    chunk_count: int

    # ── 输出 ──
    status: str          # completed | failed
    error: str

    # ── 进度 ──
    progress: int        # 0-100
    stage: str           # 当前阶段名


# ============================================================================
# 图构建
# ============================================================================

_compiled_import_graph: CompiledStateGraph | None = None


def build_import_graph() -> CompiledStateGraph:
    """构建并编译导入管道图（单例）"""
    global _compiled_import_graph
    if _compiled_import_graph is not None:
        return _compiled_import_graph

    from app.nodes.importer.validate import node_validate, route_after_validate
    from app.nodes.importer.split import node_split
    from app.nodes.importer.create_unit import node_create_unit
    from app.nodes.importer.upload_all import node_upload_all
    from app.nodes.importer.parse_all import node_parse_all
    from app.nodes.importer.enrich_images import node_enrich_images
    from app.nodes.importer.chunk import node_chunk
    from app.nodes.importer.vectorize import node_vectorize
    from app.nodes.importer.update import node_update

    builder = StateGraph(ImportState)

    builder.add_node("validate", node_validate)
    builder.add_node("split", node_split)
    builder.add_node("create_unit", node_create_unit)
    builder.add_node("upload_all", node_upload_all)
    builder.add_node("parse_all", node_parse_all)
    builder.add_node("enrich_images", node_enrich_images)
    builder.add_node("chunk", node_chunk)
    builder.add_node("vectorize", node_vectorize)
    builder.add_node("update", node_update)

    builder.set_entry_point("validate")
    builder.add_conditional_edges("validate", route_after_validate, {"failed": END, "split": "split", "direct": "create_unit"})
    builder.add_edge("split", "create_unit")
    builder.add_edge("create_unit", "upload_all")
    builder.add_edge("upload_all", "parse_all")
    builder.add_edge("parse_all", "enrich_images")
    builder.add_edge("enrich_images", "chunk")
    builder.add_edge("chunk", "vectorize")
    builder.add_edge("vectorize", "update")
    builder.add_edge("update", END)

    _compiled_import_graph = builder.compile()
    return _compiled_import_graph


async def run_import_graph(state: ImportState) -> ImportState:
    """执行导入管道图，返回最终状态"""
    graph = build_import_graph()
    result = await graph.ainvoke(state)
    return result