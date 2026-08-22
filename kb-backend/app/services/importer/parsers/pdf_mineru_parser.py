import subprocess
import tempfile
import os
from app.services.importer.parsers.base import BaseParser


class PdfMineruParser(BaseParser):
    """
    复杂排版 PDF 解析器——调用 MinerU 将 PDF 转为结构化 Markdown。
    前提：MinerU 已通过 Docker 或本地部署，提供 CLI 或 HTTP 接口。
    这里以 CLI 调用为例（magic-pdf 命令）。
    """

    def parse(self, file_path: str) -> str:
        with tempfile.TemporaryDirectory() as tmpdir:
            cmd = [
                "magic-pdf",
                "-p", file_path,
                "-o", tmpdir,
                "-m", "auto",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if result.returncode != 0:
                raise RuntimeError(f"MinerU 解析失败: {result.stderr}")

            # MinerU 输出目录结构: {tmpdir}/{filename}/{filename}.md
            basename = os.path.splitext(os.path.basename(file_path))[0]
            md_path = os.path.join(tmpdir, basename, f"{basename}.md")
            if not os.path.exists(md_path):
                # 尝试自动模式输出路径
                auto_dir = os.path.join(tmpdir, "auto")
                md_path = os.path.join(auto_dir, f"{basename}.md")

            if os.path.exists(md_path):
                with open(md_path, "r", encoding="utf-8") as f:
                    return f.read()

            raise FileNotFoundError(f"MinerU 输出文件未找到: {md_path}")