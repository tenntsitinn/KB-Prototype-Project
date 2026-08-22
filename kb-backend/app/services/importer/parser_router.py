from enum import Enum
import fitz  # PyMuPDF
from app.services.importer.parsers.base import BaseParser
from app.services.importer.parsers.txt_parser import TxtParser
from app.services.importer.parsers.markdown_parser import MarkdownParser
from app.services.importer.parsers.docx_parser import DocxParser
from app.services.importer.parsers.pdf_text_parser import PdfTextParser
from app.services.importer.parsers.pdf_mineru_parser import PdfMineruParser
from app.services.importer.parsers.pdf_ocr_parser import PdfOcrParser
from app.services.importer.parsers.pdf_unlimited_ocr_parser import PdfUnlimitedOcrParser


class FileType(str, Enum):
    TXT = "txt"
    MD = "md"
    DOCX = "docx"
    PDF = "pdf"
    UNKNOWN = "unknown"


class PDFType(str, Enum):
    TEXT = "text"           # 文字型，文本覆盖率 > 80%
    COMPLEX = "complex"     # 复杂排版，含表格/多栏/公式
    SCANNED = "scanned"     # 扫描件，文本覆盖率 < 10%


def detect_format(filename: str) -> FileType:
    """从文件名推断格式类型"""
    lower = filename.lower()
    if lower.endswith((".md", ".markdown")):
        return FileType.MD
    if lower.endswith(".txt"):
        return FileType.TXT
    if lower.endswith((".docx", ".doc")):
        return FileType.DOCX
    if lower.endswith(".pdf"):
        return FileType.PDF
    return FileType.UNKNOWN


def detect_pdf_type(file_path: str) -> PDFType:
    """
    检测 PDF 类型：
    1. 扫描每页，计算文本覆盖率
    2. 覆盖率 > 80% → 文字型
    3. 覆盖率 < 10% → 扫描件
    4. 检测到表格/多栏标记 → 复杂排版
    """
    doc = fitz.open(file_path)
    total_chars = 0
    estimated_image_chars = 0
    has_table = False
    has_multicol = False

    for page in doc:
        text = page.get_text("text")
        total_chars += len(text.strip())

        # 检测表格标记（PyMuPDF 的 table 检测）
        tabs = page.find_tables()
        if tabs and len(tabs.tables) > 0:
            has_table = True

        # 检测多栏：文本框数量多且 X 坐标分散
        blocks = page.get_text("blocks")
        if len(blocks) > 8:
            x_coords = [b[0] for b in blocks if b[6] == 0]  # type 0 = text
            if len(x_coords) >= 3:
                x_range = max(x_coords) - min(x_coords)
                if x_range > 200:
                    has_multicol = True

        # 扫描件估算：检查页面图片数量
        images = page.get_images()
        estimated_image_chars += len(images) * 500

    doc.close()

    total_estimated = total_chars + estimated_image_chars
    if total_estimated == 0:
        return PDFType.SCANNED

    text_ratio = total_chars / total_estimated

    if has_table or has_multicol:
        return PDFType.COMPLEX
    if text_ratio > 0.8:
        return PDFType.TEXT
    if text_ratio < 0.1:
        return PDFType.SCANNED
    return PDFType.COMPLEX


def route_parser(
    file_type: FileType,
    pdf_type: PDFType | None = None,
    use_unlimited_ocr: bool = False,
) -> BaseParser:
    """根据文件类型和 PDF 子类型路由到对应解析器。

    use_unlimited_ocr: 当为 True 时，所有 PDF 统一使用 Unlimited-OCR (需 GPU)，
    不再进行文字型/扫描件/复杂排版的分流。
    """
    if file_type == FileType.TXT:
        return TxtParser()
    if file_type == FileType.MD:
        return MarkdownParser()
    if file_type == FileType.DOCX:
        return DocxParser()
    if file_type == FileType.PDF:
        if use_unlimited_ocr:
            return PdfUnlimitedOcrParser()
        # 本地开发环境：无 magic-pdf / OCR 工具，统一用 PyMuPDF 提取文本
        return PdfTextParser()
    raise ValueError(f"不支持的文件类型: {file_type}")


def parse_file(file_path: str, filename: str, use_unlimited_ocr: bool = False) -> str:
    """
    一站式解析入口：检测格式 → 路由解析器 → 解析。
    当 use_unlimited_ocr=True 时，PDF 统一走 Unlimited-OCR，跳过子类型检测。
    返回 Markdown 格式文本。
    """
    file_type = detect_format(filename)
    if file_type == FileType.PDF:
        if use_unlimited_ocr:
            pdf_type = None
        else:
            pdf_type = None  # 本地开发走 PdfTextParser，无需检测
    else:
        pdf_type = None
    parser = route_parser(file_type, pdf_type, use_unlimited_ocr=use_unlimited_ocr)
    return parser.parse(file_path)