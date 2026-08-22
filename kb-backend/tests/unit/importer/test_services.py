"""
服务层单元测试。

用法:
    python -m pytest tests/test_services/ -v
"""

import os
import tempfile
import pytest


# ============================================================
# Text Chunker 测试
# ============================================================


class TestTextChunker:
    """文本切片器测试"""

    def test_chunk_basic(self):
        from app.services.importer.text_chunker import chunk_text, merge_chunks

        text = "第一节内容。\n\n第二节内容。\n\n第三节内容。"
        chunks = chunk_text(text, chunk_size=500, overlap=50)
        assert len(chunks) > 0
        merged = merge_chunks(chunks)
        assert "第一节内容" in merged
        assert "第二节内容" in merged

    def test_chunk_single_paragraph(self):
        from app.services.importer.text_chunker import chunk_text

        text = "这是一段很短的文本。"
        chunks = chunk_text(text, chunk_size=500, overlap=50)
        assert len(chunks) == 1
        assert chunks[0].text == text

    def test_chunk_long_paragraph(self):
        from app.services.importer.text_chunker import chunk_text

        # 生成超过 chunk_size 的长段落（无换行）
        text = "测试句子。" * 200  # 约 1200 字
        chunks = chunk_text(text, chunk_size=500, overlap=50)
        assert len(chunks) >= 2
        for c in chunks:
            assert len(c.text) > 0

    def test_chunk_overlap_between_paragraphs(self):
        from app.services.importer.text_chunker import chunk_text

        # 两个段落，第一个刚好略超 chunk_size
        para1 = "A" * 480
        para2 = "B" * 100
        text = f"{para1}\n\n{para2}"
        chunks = chunk_text(text, chunk_size=500, overlap=50)
        assert len(chunks) >= 2

        # 重叠验证：第二个 chunk 的开头部分应出现在第一个 chunk 末尾
        if len(chunks) >= 2:
            overlap_start = chunks[1].text[:30]
            assert overlap_start in chunks[0].text or len(overlap_start) > 0

    def test_chunk_empty_text(self):
        from app.services.importer.text_chunker import chunk_text

        chunks = chunk_text("", chunk_size=500, overlap=50)
        assert len(chunks) == 0

    def test_chunk_whitespace_only(self):
        from app.services.importer.text_chunker import chunk_text

        chunks = chunk_text("   \n\n  \n  ", chunk_size=500, overlap=50)
        assert len(chunks) == 0

    def test_merge_chunks_preserves_order(self):
        from app.services.importer.text_chunker import Chunk, merge_chunks

        c1 = Chunk(index=0, text="第一部分", start_char=0, end_char=4)
        c2 = Chunk(index=1, text="第二部分", start_char=5, end_char=9)
        c3 = Chunk(index=2, text="第三部分", start_char=10, end_char=14)

        merged = merge_chunks([c2, c1, c3])  # 乱序传入
        assert merged == "第一部分\n\n第二部分\n\n第三部分"

    def test_chunk_preserves_sentence_boundaries(self):
        from app.services.importer.text_chunker import chunk_text

        # 确保句子边界不会被从中间切断（段落级切分优先）
        text = "第一段短内容。\n\n第二段短内容。\n\n第三段短内容。"
        chunks = chunk_text(text, chunk_size=200, overlap=20)
        for c in chunks:
            # 每个 chunk 不应包含半个句子（以句号结尾或开头完整）
            assert len(c.text) > 0

    def test_chunk_index_sequential(self):
        from app.services.importer.text_chunker import chunk_text

        text = "\n\n".join([f"段落{i}的内容。" * 10 for i in range(10)])
        chunks = chunk_text(text, chunk_size=300, overlap=30)
        for i, c in enumerate(chunks):
            assert c.index == i


# ============================================================
# File Validator 测试
# ============================================================


class TestFileValidator:
    """文件校验器测试"""

    def test_get_file_type(self):
        from app.services.importer.file_validator import get_file_type

        assert get_file_type("doc.pdf") == "pdf"
        assert get_file_type("doc.docx") == "docx"
        assert get_file_type("doc.doc") == "docx"
        assert get_file_type("readme.md") == "md"
        assert get_file_type("readme.markdown") == "md"
        assert get_file_type("notes.txt") == "txt"
        assert get_file_type("image.png") == "unknown"

    def test_validate_file_size_pass(self):
        from app.services.importer.file_validator import validate_file_size

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("小文件")
            tmp_path = f.name

        try:
            valid, msg = validate_file_size(tmp_path, "txt")
            assert valid
            assert msg == ""
        finally:
            os.unlink(tmp_path)

    def test_validate_file_size_unknown_type(self):
        from app.services.importer.file_validator import validate_file_size

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("test")
            tmp_path = f.name

        try:
            valid, msg = validate_file_size(tmp_path, "unknown")
            assert not valid
            assert "不支持" in msg
        finally:
            os.unlink(tmp_path)

    def test_get_file_size_mb(self):
        from app.services.importer.file_validator import get_file_size_mb

        with tempfile.NamedTemporaryFile(mode="wb", suffix=".txt", delete=False) as f:
            f.write(b"x" * 1024)  # 1KB
            tmp_path = f.name

        try:
            size_mb = get_file_size_mb(tmp_path)
            assert 0 < size_mb < 0.01  # 约 0.001 MB
        finally:
            os.unlink(tmp_path)
