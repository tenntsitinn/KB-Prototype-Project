from docx import Document
from app.services.importer.parsers.base import BaseParser


class DocxParser(BaseParser):
    """Word (.docx) 解析器——提取段落文本，段落间用双换行分隔"""

    def parse(self, file_path: str) -> str:
        doc = Document(file_path)
        paragraphs: list[str] = []
        for para in doc.paragraphs:
            text = para.text.strip()
            if text:
                # 根据段落样式推断标题层级
                style_name = (para.style.name or "") if para.style is not None else ""
                if style_name.startswith("Heading"):
                    level = style_name.split()[-1]
                    try:
                        level_num = int(level)
                        paragraphs.append(f"{'#' * level_num} {text}")
                    except ValueError:
                        paragraphs.append(f"## {text}")
                else:
                    paragraphs.append(text)
        return "\n\n".join(paragraphs)
