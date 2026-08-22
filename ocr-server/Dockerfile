FROM pytorch/pytorch:2.2.0-cuda12.1-cudnn8-runtime

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .

EXPOSE 8000

ENV OCR_MODEL_NAME=baidu/Unlimited-OCR
ENV OCR_DPI=300
ENV OCR_IMAGE_SIZE=1024
ENV OCR_MAX_LENGTH=32768
ENV OCR_MAX_FILE_MB=100

# 首次启动时 HuggingFace 会自动下载模型到 ~/.cache/huggingface
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]