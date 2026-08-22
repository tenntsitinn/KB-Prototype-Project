"""
Unlimited-OCR 解析器（百度 VLM 模型）

支持两种模式：
- 本地模式（UNLIMITED_OCR_URL 为空）：加载模型到本进程，直接调用
- 远程模式（UNLIMITED_OCR_URL 非空）：发送 PDF 到独立 OCR 服务，等待返回

OCR 服务端点: POST {UNLIMITED_OCR_URL}/ocr
  请求: multipart/form-data, file 字段为 PDF 文件
  响应: {"text": "...", "pages": 3, "elapsed_ms": 12345}
"""

import logging
import os
import tempfile
import time
from typing import Optional

import requests
import fitz

from app.config import settings
from app.services.importer.parsers.base import BaseParser

logger = logging.getLogger(__name__)


class PdfUnlimitedOcrParser(BaseParser):
    def __init__(
        self,
        model_name: str = "baidu/Unlimited-OCR",
        dpi: int = 300,
        image_size: int = 1024,
        max_length: int = 32768,
    ):
        self._model_name = model_name
        self._dpi = dpi
        self._image_size = image_size
        self._max_length = max_length
        self._model: Optional[object] = None
        self._tokenizer: Optional[object] = None

    # ------------------------------------------------------------------
    # 公共入口
    # ------------------------------------------------------------------

    def parse(self, file_path: str) -> str:
        if settings.UNLIMITED_OCR_URL:
            return self._parse_remote(file_path)
        return self._parse_local(file_path)

    # ------------------------------------------------------------------
    # 远程模式
    # ------------------------------------------------------------------

    def _parse_remote(self, file_path: str) -> str:
        url = f"{settings.UNLIMITED_OCR_URL.rstrip('/')}/ocr"
        logger.info("Unlimited-OCR 远程调用: %s", url)

        with open(file_path, "rb") as f:
            resp = requests.post(url, files={"file": f}, timeout=600)

        if resp.status_code != 200:
            raise RuntimeError(f"OCR 服务返回错误 {resp.status_code}: {resp.text}")

        data = resp.json()
        text = data.get("text", "")
        logger.info("Unlimited-OCR 远程完成: %d 字符, %dms", len(text), data.get("elapsed_ms", 0))
        return text

    # ------------------------------------------------------------------
    # 本地模式
    # ------------------------------------------------------------------

    def _ensure_model(self):
        if self._model is not None:
            return

        try:
            import torch
            from transformers import AutoModel, AutoTokenizer
        except ImportError:
            raise ImportError(
                "Unlimited-OCR 依赖未安装，请执行:\n"
                "pip install torch torchvision transformers Pillow einops "
                "addict easydict pymupdf psutil matplotlib"
            )

        if not torch.cuda.is_available():
            raise RuntimeError("Unlimited-OCR 本地模式需要 NVIDIA GPU + CUDA，或设置 UNLIMITED_OCR_URL 使用远程服务")

        logger.info("加载 Unlimited-OCR 模型: %s", self._model_name)
        self._tokenizer = AutoTokenizer.from_pretrained(
            self._model_name, trust_remote_code=True
        )
        self._model = AutoModel.from_pretrained(
            self._model_name,
            trust_remote_code=True,
            use_safetensors=True,
            torch_dtype=torch.bfloat16,
        )
        self._model = self._model.eval().cuda()
        logger.info("Unlimited-OCR 模型加载完成")

    @staticmethod
    def _pdf_to_images(pdf_path: str, dpi: int = 300) -> list[str]:
        doc = fitz.open(pdf_path)
        tmp_dir = tempfile.mkdtemp(prefix="unlimited_ocr_")
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        paths = []
        for i, page in enumerate(doc):
            out = os.path.join(tmp_dir, f"page_{i + 1:04d}.png")
            page.get_pixmap(matrix=mat).save(out)
            paths.append(out)
        doc.close()
        return paths

    def _parse_local(self, file_path: str) -> str:
        self._ensure_model()

        image_paths = self._pdf_to_images(file_path, dpi=self._dpi)
        if not image_paths:
            raise RuntimeError(f"PDF 无页面: {file_path}")

        logger.info("Unlimited-OCR 本地开始解析 %d 页", len(image_paths))

        output_dir = tempfile.mkdtemp(prefix="ocr_output_")
        try:
            result = self._model.infer_multi(
                self._tokenizer,
                prompt="<image>Multi page parsing.",
                image_files=image_paths,
                output_path=output_dir,
                image_size=self._image_size,
                max_length=self._max_length,
                no_repeat_ngram_size=35,
                ngram_window=1024,
                save_results=False,
            )
        finally:
            for p in image_paths:
                try:
                    os.unlink(p)
                except OSError:
                    pass
            img_dir = os.path.dirname(image_paths[0]) if image_paths else None
            if img_dir and os.path.isdir(img_dir):
                try:
                    os.rmdir(img_dir)
                except OSError:
                    pass
            try:
                os.rmdir(output_dir)
            except OSError:
                pass

        if isinstance(result, list):
            text = "\n\n".join(result)
        else:
            text = str(result)

        logger.info("Unlimited-OCR 本地完成: %d 字符", len(text))
        return text