from app.services.importer.parsers.base import BaseParser


class TxtParser(BaseParser):
    """TXT 纯文本解析器"""

    def parse(self, file_path: str) -> str:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()