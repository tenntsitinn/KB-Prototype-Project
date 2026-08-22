from abc import ABC, abstractmethod


class BaseParser(ABC):
    """解析器基类，所有格式解析器必须实现 parse 方法"""

    @abstractmethod
    def parse(self, file_path: str) -> str:
        """解析文件，返回 Markdown 格式的纯文本"""
        ...