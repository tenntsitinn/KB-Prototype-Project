"""
Unlimited-OCR 独立服务端（部署在 AutoDL GPU 实例上）

启动: uvicorn ocr_server:app --host 0.0.0.0 --port 8000
调用: POST /ocr  multipart/form-data, file=xxx.pdf
返回: {"text": "...", "pages": 3, "elapsed_ms": 12345}
"""

import os
import tempfile
import time
import logging

import fitz
from fastapi import FastAPI, File, UploadFile, HTTPException

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("ocr_server")

app = FastAPI(title="OCR Server", version="1.0")

# ---- 全局模型缓存 ----
_model = None
_tokenizer = None

MODEL_NAME = os.getenv("OCR_MODEL_NAME", "baidu/Unlimited-OCR")
DPI = int(os.getenv("OCR_DPI", "300"))
IMAGE_SIZE = int(os.getenv("OCR_IMAGE_SIZE", "1024"))
MAX_LENGTH = int(os.getenv("OCR_MAX_LENGTH", "32768"))


def _load_model():
    global _model, _tokenizer
    if _model is not None:
        return

    import torch
    from transformers import AutoModel, AutoTokenizer

    if not torch.cuda.is_available():
        raise RuntimeError("需要 NVIDIA GPU + CUDA")

    logger.info("加载模型: %s", MODEL_NAME)
    _tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, trust_remote_code=True, local_files_only=True)
    _model = AutoModel.from_pretrained(
        MODEL_NAME,
        trust_remote_code=True,
        use_safetensors=True,
        torch_dtype=torch.bfloat16,
        local_files_only=True,
    )
    _model = _model.eval().cuda()
    logger.info("模型加载完成")


@app.on_event("startup")
def startup():
    _load_model()


@app.get("/health")
def health():
    return {"status": "ok", "model": MODEL_NAME, "gpu_available": _model is not None}


@app.post("/ocr")
async def ocr(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "仅支持 PDF 文件")

    t0 = time.time()

    # 保存上传的 PDF 到临时文件
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(await file.read())
        pdf_path = tmp.name

    try:
        # PDF → 图片
        image_paths = _pdf_to_images(pdf_path, dpi=DPI)
        if not image_paths:
            raise HTTPException(400, "PDF 无页面")

        logger.info("解析 %d 页", len(image_paths))

        # 推理
        output_dir = tempfile.mkdtemp(prefix="ocr_output_")
        result = _model.infer_multi(
            _tokenizer,
            "<image>Multi page parsing.",
            image_paths,
            output_dir,
            IMAGE_SIZE,
            False,
            MAX_LENGTH,
            0,
            35,
            1024,
        )

        if isinstance(result, list):
            text = "\n\n".join(result)
        else:
            text = str(result)

        elapsed_ms = int((time.time() - t0) * 1000)
        logger.info("完成: %d 字符, %dms", len(text), elapsed_ms)

        return {"text": text, "pages": len(image_paths), "elapsed_ms": elapsed_ms}

    finally:
        # 清理临时文件
        for p in image_paths if "image_paths" in dir() else []:
            try:
                os.unlink(p)
            except OSError:
                pass
        img_dir = os.path.dirname(image_paths[0]) if image_paths and os.path.isdir(
            os.path.dirname(image_paths[0])
        ) else None
        if img_dir:
            try:
                os.rmdir(img_dir)
            except OSError:
                pass
        if "output_dir" in dir():
            try:
                os.rmdir(output_dir)
            except OSError:
                pass
        try:
            os.unlink(pdf_path)
        except OSError:
            pass


def _pdf_to_images(pdf_path: str, dpi: int = 300) -> list[str]:
    doc = fitz.open(pdf_path)
    tmp_dir = tempfile.mkdtemp(prefix="ocr_")
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