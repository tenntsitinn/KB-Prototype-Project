import re
from dataclasses import dataclass
from app.config import settings


@dataclass
class Chunk:
    index: int
    text: str
    start_char: int
    end_char: int


def _tail_overlap(current: str, overlap: int) -> str:
    """取上一块尾部作为重叠。overlap=0 时必须返回空串：
    `current[-0:]` 等价于 `current[0:]`（整串），会让块无限滚雪球增长"""
    if overlap <= 0:
        return ""
    return current[-overlap:] if len(current) > overlap else current


def chunk_text(text: str, chunk_size: int | None = None, overlap: int | None = None) -> list[Chunk]:
    """
    将文本切分为固定大小的块，带重叠。
    策略：优先按段落边界切，段内按句子边界切，最后按字符硬切。
    """
    chunk_size = chunk_size or settings.CHUNK_SIZE
    overlap = overlap or settings.CHUNK_OVERLAP

    paragraphs = _split_paragraphs(text)
    chunks: list[Chunk] = []
    current = ""
    idx = 0

    for para in paragraphs:
        if len(current) + len(para) <= chunk_size:
            current += para + "\n\n"
        else:
            if current.strip():
                chunks.append(_make_chunk(idx, current.strip()))
                idx += 1
                # 重叠：保留上一块的尾部
                current = _tail_overlap(current, overlap) + para + "\n\n"
            else:
                # 单段超过 chunk_size，按句子硬切
                for sub in _split_long_paragraph(para, chunk_size, overlap):
                    chunks.append(_make_chunk(idx, sub.strip()))
                    idx += 1
                current = ""

    if current.strip():
        chunks.append(_make_chunk(idx, current.strip()))

    return chunks


def merge_chunks(chunks: list[Chunk]) -> str:
    """将多个 Chunk 按 index 顺序合并为完整文本"""
    sorted_chunks = sorted(chunks, key=lambda c: c.index)
    return "\n\n".join(c.text for c in sorted_chunks)


def _split_paragraphs(text: str) -> list[str]:
    """按连续换行符切分为段落"""
    return [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]


def _split_long_paragraph(text: str, chunk_size: int, overlap: int) -> list[str]:
    """将超长段落按句子边界切分"""
    sentences = _split_sentences(text)
    chunks: list[str] = []
    current = ""

    for sent in sentences:
        if len(current) + len(sent) <= chunk_size:
            current += sent
        else:
            if current.strip():
                chunks.append(current.strip())
                current = _tail_overlap(current, overlap) + sent
            else:
                # 单句超过 chunk_size，硬切
                for i in range(0, len(sent), max(chunk_size - overlap, 1)):
                    chunks.append(sent[i:i + chunk_size].strip())
                current = ""

    if current.strip():
        chunks.append(current.strip())
    return chunks


def _split_sentences(text: str) -> list[str]:
    """按中英文标点切分句子"""
    return re.split(r"(?<=[。！？.!?])\s*", text)


def _make_chunk(index: int, text: str) -> Chunk:
    return Chunk(index=index, text=text, start_char=0, end_char=len(text))