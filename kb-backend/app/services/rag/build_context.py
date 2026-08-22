"""构建 LLM 上下文"""
import re
from app.graphs.rag_graph import RAGState


def _extract_images(text: str) -> list[str]:
    """从文本中提取所有 markdown 图片引用 ![...](...)"""
    return re.findall(r"!\[.*?\]\([^)]+\)", text)


def _wrap_latex_math(text: str) -> str:
    """将文本中的 LaTeX 数学表达式（\command、下划线/上标变量）包裹在 $...$ 中"""
    # 保护已有的 $$...$$ 和 $...$ 块
    protected: list[str] = []

    def _protect(m: re.Match) -> str:
        protected.append(m.group(0))
        return f"\x00PROTECT{len(protected) - 1}\x00"

    text = re.sub(r"\$\$[^$]+\$\$", _protect, text)
    text = re.sub(r"\$[^$]+\$", _protect, text)

    # 包裹 LaTeX 命令：\command{...} 或 \command
    text = re.sub(r"(\\[a-zA-Z]+\{[^}]*\})", r"$\1$", text)
    text = re.sub(r"(\\[a-zA-Z]+)", r"$\1$", text)

    # 包裹下划线/上标变量：word_{sub} 或 word^{sup}
    text = re.sub(r"([A-Za-z0-9])_\{([^}]+)\}", r"$\1_{\2}$", text)
    text = re.sub(r"([A-Za-z0-9])\^\{([^}]+)\}", r"$\1^{\2}$", text)

    # 恢复保护块
    for i, p in enumerate(protected):
        text = text.replace(f"\x00PROTECT{i}\x00", p)

    return text


def do_build_context(state: RAGState) -> dict:
    chunks = state["final_chunks"]
    if not chunks:
        return {"context": "（知识库中未找到相关内容）", "context_images": []}

    parts = []
    all_images: list[str] = []
    seen_images: set[str] = set()

    for i, c in enumerate(chunks):
        chunk_text = _wrap_latex_math(c.chunk_text)
        parts.append(f"[来源{i + 1}] (unit_code: {c.unit_code})\n{chunk_text}")
        for img in _extract_images(chunk_text):
            if img not in seen_images:
                seen_images.add(img)
                all_images.append(img)

    return {"context": "\n\n---\n\n".join(parts), "context_images": all_images}