"""
Unlimited-OCR 独立推理服务。

启动: uvicorn server:app --host 0.0.0.0 --port 8000

端点:
  POST /ocr  上传 PDF 文件，返回结构化 Markdown 文本
  GET  /health  健康检查
"""

import logging
import os
import tempfile
import time
from contextlib import asynccontextmanager

import fitz
from fastapi import FastAPI, File, UploadFile, HTTPException

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ocr-server")

MODEL_NAME = os.getenv("OCR_MODEL_NAME", "baidu/Unlimited-OCR")
DPI = int(os.getenv("OCR_DPI", "300"))
IMAGE_SIZE = int(os.getenv("OCR_IMAGE_SIZE", "1024"))
MAX_LENGTH = int(os.getenv("OCR_MAX_LENGTH", "32768"))
MAX_FILE_MB = int(os.getenv("OCR_MAX_FILE_MB", "100"))

model = None
tokenizer = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global model, tokenizer

    import torch
    from transformers import AutoModel, AutoTokenizer

    if not torch.cuda.is_available():
        raise RuntimeError("Unlimited-OCR 需要 NVIDIA GPU + CUDA")

    logger.info("加载 Unlimited-OCR 模型: %s", MODEL_NAME)
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, trust_remote_code=True)
    model = AutoModel.from_pretrained(
        MODEL_NAME,
        trust_remote_code=True,
        use_safetensors=True,
        torch_dtype=torch.bfloat16,
    )
    model = model.eval().cuda()
    logger.info("模型加载完成，服务就绪")
    yield


app = FastAPI(title="Unlimited-OCR Server", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok", "model": MODEL_NAME, "gpu": model is not None}


@app.post("/ocr")
async def ocr(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "仅支持 PDF 文件")

    contents = await file.read()
    if len(contents) > MAX_FILE_MB * 1024 * 1024:
        raise HTTPException(400, f"文件大小超过限制 ({MAX_FILE_MB}MB)")

    t0 = time.time()

    # 写入临时文件
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".pdf", prefix="ocr_")
    try:
        with os.fdopen(tmp_fd, "wb") as f:
            f.write(contents)

        # 渲染为图片
        image_paths = _pdf_to_images(tmp_path, DPI)
        if not image_paths:
            raise HTTPException(400, "PDF 无页面")

        logger.info("开始解析 %d 页, 文件: %s", len(image_paths), file.filename)

        output_dir = tempfile.mkdtemp(prefix="ocr_output_")
        result = model.infer_multi(
            tokenizer,
            prompt="<image>Multi page parsing.",
            image_files=image_paths,
            output_path=output_dir,
            image_size=IMAGE_SIZE,
            max_length=MAX_LENGTH,
            no_repeat_ngram_size=35,
            ngram_window=1024,
            save_results=False,
        )

        # 清理图片
        for p in image_paths:
            try:
                os.unlink(p)
            except OSError:
                pass
        img_dir = os.path.dirname(image_paths[0])
        try:
            os.rmdir(img_dir)
        except OSError:
            pass
        try:
            os.rmdir(output_dir)
        except OSError:
            pass

    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    if isinstance(result, list):
        text = "\n\n".join(result)
    else:
        text = str(result)

    elapsed_ms = int((time.time() - t0) * 1000)
    logger.info("解析完成: %d 字符, %dms", len(text), elapsed_ms)

    return {"text": text, "pages": len(image_paths), "elapsed_ms": elapsed_ms}


def _pdf_to_images(pdf_path: str, dpi: int = 300) -> list[str]:
    doc = fitz.open(pdf_path)
    tmp_dir = tempfile.mkdtemp(prefix="ocr_img_")
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    paths = []
    for i, page in enumerate(doc):
        out = os.path.join(tmp_dir, f"page_{i + 1:04d}.png")
        page.get_pixmap(matrix=mat).save(out)
        paths.append(out)
    doc.close()
    return paths


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)