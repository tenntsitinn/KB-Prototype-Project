"""
知识点提取管道 LangGraph 状态图。

从文档切片（knowledge_chunks）中用 LLM 提取知识点（topic + 描述），
按 topic 聚合 delta，每 POINT_REWRITE_INTERVAL 个 chunk 批量执行一次
「匹配 → 重写 → 落库」，文档结束后最后一次 flush 兜底，
全部结果进入 pending_review 等待人工审核。

图结构:
  START → load_chunks → extract ⇄ (每 20 chunk / 文档结束) → flush → finalize → END

本文件包含：状态类型定义、图构建。
节点函数在 app/nodes/extraction/。
"""
import logging
from typing import TypedDict

from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph

logger = logging.getLogger(__name__)


# ============================================================================
# 图状态
# ============================================================================


class PointExtractionState(TypedDict, total=False):
    """知识点提取管道状态，在节点间传递"""

    # ── 输入 ──
    unit_id: str        # 知识单元（文档）ID
    api_key: str        # LLM key（BYOK 优先，回退全局）
    base_url: str       # LLM base_url
    model: str          # LLM 模型名
    force: bool         # True 时忽略已完成的提取状态重跑

    # ── 中间结果 ──
    chunks: list[dict]       # [{chunk_index, chunk_text}]
    cursor: int              # 当前处理的 chunk 下标
    since_flush: int         # 距上次 flush 处理的 chunk 数
    topic_acc: dict[str, dict]  # 窗口内按 topic 聚合: {topic: {raw_delta, chunk_indices}}
    stats: dict              # {chunks, auto_merged, candidates, created}

    # ── 输出 ──
    status: str         # completed | failed | skipped
    error: str
    stage: str


# ============================================================================
# 图构建
# ============================================================================

_compiled_extraction_graph: CompiledStateGraph | None = None


def build_point_extraction_graph() -> CompiledStateGraph:
    """构建并编译知识点提取图（单例）"""
    global _compiled_extraction_graph
    if _compiled_extraction_graph is not None:
        return _compiled_extraction_graph

    from app.nodes.extraction.load_chunks import node_load_chunks, route_after_load
    from app.nodes.extraction.extract_topics import node_extract_topics, route_after_extract
    from app.nodes.extraction.flush import node_flush, route_after_flush
    from app.nodes.extraction.finalize import node_finalize

    builder = StateGraph(PointExtractionState)

    builder.add_node("load_chunks", node_load_chunks)
    builder.add_node("extract", node_extract_topics)
    builder.add_node("flush", node_flush)
    builder.add_node("finalize", node_finalize)

    builder.set_entry_point("load_chunks")
    builder.add_conditional_edges("load_chunks", route_after_load, {
        "failed": END,
        "skipped": END,
        "empty": "finalize",
        "run": "extract",
    })
    builder.add_conditional_edges("extract", route_after_extract, {
        "loop": "extract",
        "flush": "flush",
    })
    builder.add_conditional_edges("flush", route_after_flush, {
        "loop": "extract",
        "finalize": "finalize",
    })
    builder.add_edge("finalize", END)

    _compiled_extraction_graph = builder.compile()
    return _compiled_extraction_graph


async def run_point_extraction_graph(state: PointExtractionState) -> PointExtractionState:
    """执行知识点提取图，返回最终状态"""
    graph = build_point_extraction_graph()
    result = await graph.ainvoke(state)
    return result
