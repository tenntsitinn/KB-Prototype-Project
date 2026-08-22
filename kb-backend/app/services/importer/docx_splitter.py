"""DOCX 流式拆分——zipfile + lxml.iterparse，不全量载入内存"""
import os
import zipfile
import logging
from lxml import etree
from app.config import settings

logger = logging.getLogger(__name__)

_KB = 1024
_MB = 1024 * _KB


def should_split_docx(file_path: str) -> bool:
    """判断 docx 是否需要拆分（超过 MAX_SIZE_DOCX 上限）"""
    return os.path.getsize(file_path) > settings.MAX_SIZE_DOCX * _MB


def split_docx(file_path: str, output_dir: str) -> list[str]:
    """
    将超限 docx 流式拆分，每份控制在 MAX_SIZE_DOCX 以内。
    用 zipfile 打开 + lxml.iterparse 逐段落读取，不全量载入内存。
    返回拆分后的子文件路径列表。
    """
    splitter = _DocxSplitter(file_path)
    return splitter.run(output_dir)


class _DocxSplitter:
    """流式 DOCX 拆分器：逐段落读取，按大小阈值写出子文件"""

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.base_name = os.path.splitext(os.path.basename(file_path))[0]
        self.shared: dict[str, bytes] = {}
        self.nsmap: dict | None = None
        self.sect_pr_xml: str | None = None

    def run(self, output_dir: str) -> list[str]:
        self._load_shared_parts()
        os.makedirs(output_dir, exist_ok=True)
        return self._stream_split(output_dir)

    def _load_shared_parts(self):
        """读取除 document.xml 外的所有部件（原样复制，保证引用完整性）"""
        with zipfile.ZipFile(self.file_path, "r") as zin:
            for name in zin.namelist():
                if name == "word/document.xml":
                    continue
                self.shared[name] = zin.read(name)

    def _stream_split(self, output_dir: str) -> list[str]:
        """流式解析 document.xml，按段落批次写出子文件"""
        target_xml_bytes = settings.MAX_SIZE_DOCX * _MB * settings.DOCX_SPLIT_BUFFER

        chunk_paths: list[str] = []
        batch_paras: list[str] = []
        batch_size = 0
        part_idx = 0
        nsmap_captured = False

        with zipfile.ZipFile(self.file_path, "r") as zin:
            doc_stream = zin.open("word/document.xml")
            context = etree.iterparse(doc_stream, events=("start", "end"))

            for event, elem in context:
                if event == "start":
                    if not nsmap_captured:
                        self.nsmap = dict(elem.nsmap)
                        nsmap_captured = True
                    continue

                tag = elem.tag
                if not isinstance(tag, str):
                    continue

                parent = elem.getparent()
                is_body_level = (
                    parent is not None
                    and isinstance(parent.tag, str)
                    and parent.tag.endswith("}body")
                )

                if not is_body_level:
                    continue

                localname = tag.rsplit("}", 1)[-1] if "}" in tag else tag

                if localname == "sectPr":
                    if self.sect_pr_xml is None:
                        self.sect_pr_xml = etree.tostring(
                            elem, encoding="unicode", with_tail=False
                        )
                else:
                    elem_xml = etree.tostring(
                        elem, encoding="unicode", with_tail=False
                    )
                    batch_paras.append(elem_xml)
                    batch_size += len(elem_xml.encode("utf-8"))

                    if batch_size >= target_xml_bytes:
                        path = self._write_part(
                            output_dir, part_idx, batch_paras
                        )
                        chunk_paths.append(path)
                        batch_paras = []
                        batch_size = 0
                        part_idx += 1

                elem.clear()
                while elem.getprevious() is not None:
                    del elem.getparent()[0]

        if batch_paras:
            path = self._write_part(output_dir, part_idx, batch_paras)
            chunk_paths.append(path)

        logger.info(
            "DOCX 拆分完成: %s → %d 个子文件",
            os.path.basename(self.file_path),
            len(chunk_paths),
        )
        return chunk_paths

    def _write_part(
        self,
        output_dir: str,
        part_idx: int,
        paras: list[str],
    ) -> str:
        """写出一份子 docx：document.xml 用拆分内容，其余部件原样复制"""
        chunk_name = f"{self.base_name}_part_{part_idx + 1:04d}.docx"
        chunk_path = os.path.join(output_dir, chunk_name)
        doc_xml = self._build_document_xml(paras)

        with zipfile.ZipFile(chunk_path, "w", zipfile.ZIP_DEFLATED) as zout:
            zout.writestr("word/document.xml", doc_xml)
            for part_path, data in self.shared.items():
                zout.writestr(part_path, data)

        logger.info(
            "写出子文件: %s (%.1fMB)",
            chunk_name,
            os.path.getsize(chunk_path) / _MB,
        )
        return chunk_path

    def _build_document_xml(self, paras: list[str]) -> str:
        """组装 document.xml 字符串"""
        ns_decls = " ".join(
            f'xmlns:{p}="{u}"' if p else f'xmlns="{u}"'
            for p, u in sorted(self.nsmap.items(), key=lambda x: x[0] or "")
        )
        header = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        body = "".join(paras)
        if self.sect_pr_xml:
            body += self.sect_pr_xml
        return f"{header}<w:document {ns_decls}><w:body>{body}</w:body></w:document>"
