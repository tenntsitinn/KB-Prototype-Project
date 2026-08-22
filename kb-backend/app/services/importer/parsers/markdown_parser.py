from app.services.importer.parsers.base import BaseParser


class MarkdownParser(BaseParser):
    """Markdown 解析器——原样返回，保留 Markdown 格式供后续切片"""

    def parse(self, file_path: str) -> str:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()