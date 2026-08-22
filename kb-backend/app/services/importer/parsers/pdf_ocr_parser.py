import logging
import tempfile
from pathlib import Path

import fitz

from app.services.importer.parsers.base import BaseParser

logger = logging.getLogger(__name__)


class PdfOcrParser(BaseParser):
    """
    扫描件 PDF 解析器——使用 PaddleOCR 逐页识别。
    前提：paddleocr 已安装 (pip install paddleocr)。
    """

    def __init__(self, lang: str = "ch", dpi: int = 200):
        self._lang = lang
        self._dpi = dpi
        self._ocr = None

    def _get_ocr(self):
        if self._ocr is None:
            try:
                from paddleocr import PaddleOCR
            except ImportError:
                raise ImportError("PaddleOCR 未安装，请执行: pip install paddleocr")
            self._ocr = PaddleOCR(lang=self._lang)
        return self._ocr

    def parse(self, file_path: str) -> str:
        ocr = self._get_ocr()
        doc = fitz.open(file_path)
        pages: list[str] = []
        failed_pages: list[int] = []

        with tempfile.TemporaryDirectory(prefix="ocr_") as tmpdir:
            for page_num in range(len(doc)):
                try:
                    page = doc[page_num]
                    pix = page.get_pixmap(dpi=self._dpi)
                    img_path = Path(tmpdir) / f"page_{page_num:04d}.png"
                    pix.save(str(img_path))

                    result = ocr.ocr(str(img_path))
                    if result and result[0]:
                        lines = [line[1][0] for line in result[0]]
                        pages.append("\n".join(lines))
                    else:
                        pages.append("")
                        logger.warning("OCR 第 %d 页无文字", page_num + 1)
                except Exception:
                    failed_pages.append(page_num + 1)
                    logger.exception("OCR 第 %d 页失败", page_num + 1)

        doc.close()

        if failed_pages:
            logger.warning(
                "OCR 完成: %d/%d 页成功, 失败页码: %s",
                len(pages),
                len(doc),
                failed_pages,
            )

        if not pages:
            raise RuntimeError(f"OCR 解析失败: 全部 {len(doc)} 页均无法识别")

        return "\n\n".join(pages)