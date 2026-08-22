import os
import fitz  # PyMuPDF
from app.config import settings

_KB = 1024
_MB = 1024 * _KB


def should_split_pdf(file_path: str) -> bool:
    """判断 PDF 是否需要拆分（超过 50MB 上限）"""
    return os.path.getsize(file_path) > settings.MAX_SIZE_PDF * _MB


def get_page_count(file_path: str) -> int:
    """获取 PDF 总页数"""
    doc = fitz.open(file_path)
    count = doc.page_count
    doc.close()
    return count


def _estimate_pages_per_chunk(file_path: str) -> int:
    """
    估算每份子 PDF 最多包含多少页，确保不超过 50MB。
    策略：总大小 / 总页数 = 每页平均大小，乘以缓冲系数反推。
    """
    total_size = os.path.getsize(file_path)
    total_pages = get_page_count(file_path)
    if total_pages == 0:
        return 1
    avg_page_size = total_size / total_pages
    max_size_per_chunk = settings.MAX_SIZE_PDF * _MB * settings.PDF_SPLIT_BUFFER
    pages = int(max_size_per_chunk / avg_page_size)
    return max(pages, 1)


def split_pdf(file_path: str, output_dir: str) -> list[str]:
    """
    将超限 PDF 按页拆分，每份控制在 50MB 以内。
    返回拆分后的子文件路径列表。
    """
    pages_per_chunk = _estimate_pages_per_chunk(file_path)
    doc = fitz.open(file_path)
    total_pages = doc.page_count
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    chunk_paths: list[str] = []

    for start in range(0, total_pages, pages_per_chunk):
        end = min(start + pages_per_chunk, total_pages)
        chunk_doc = fitz.open()
        chunk_doc.insert_pdf(doc, from_page=start, to_page=end - 1)
        chunk_name = f"{base_name}_part_{start + 1:04d}_{end:04d}.pdf"
        chunk_path = os.path.join(output_dir, chunk_name)
        chunk_doc.save(chunk_path)
        chunk_doc.close()
        chunk_paths.append(chunk_path)

    doc.close()
    return chunk_paths