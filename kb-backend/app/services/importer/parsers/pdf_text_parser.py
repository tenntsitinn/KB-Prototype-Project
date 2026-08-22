import fitz  # PyMuPDF
import os
import logging
from pathlib import Path
from app.services.importer.parsers.base import BaseParser

logger = logging.getLogger(__name__)


class PdfTextParser(BaseParser):
    """文字型 PDF 解析器——使用 PyMuPDF 提取文本 + 图片"""

    def parse(self, file_path: str) -> str:
        doc = fitz.open(file_path)
        base_dir = os.path.dirname(file_path)
        pages: list[str] = []
        total_images = 0

        for page_idx, page in enumerate(doc):
            text = page.get_text("text")
            parts = []

            images = page.get_images(full=True)
            logger.info(f"PDF 第 {page_idx+1} 页: 找到 {len(images)} 张图片")
            for img_idx, img_info in enumerate(images):
                xref = img_info[0]
                try:
                    base_image = doc.extract_image(xref)
                    if base_image:
                        ext = base_image["ext"]
                        img_filename = f"pdf_img_p{page_idx+1}_{img_idx}.{ext}"
                        img_path = str(Path(os.path.join(base_dir, img_filename)).resolve())
                        with open(img_path, "wb") as f:
                            f.write(base_image["image"])
                        parts.append(f"![{img_filename}]({img_path})")
                        total_images += 1
                except Exception as e:
                    logger.warning(f"提取图片失败 xref={xref}: {e}")

            if text.strip():
                parts.insert(0, text.strip())

            if parts:
                pages.append("\n\n".join(parts))

        doc.close()
        logger.info(f"PDF 图片提取完成: 共 {total_images} 张")
        return "\n\n".join(pages)