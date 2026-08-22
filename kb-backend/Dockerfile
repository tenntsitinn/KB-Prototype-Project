# ============================================================
# 构建阶段配置
# ============================================================
ARG PYTHON_VERSION=3.11
ARG UVICORN_PORT=8000
ARG UVICORN_WORKERS=4

# ============================================================
# Stage 1: 依赖安装
# ============================================================
FROM python:${PYTHON_VERSION}-slim-bookworm AS builder

WORKDIR /app

# 更换为腾讯云镜像源
RUN sed -i 's/deb.debian.org/mirrors.tencentyun.com/g' /etc/apt/sources.list.d/debian.sources

# 系统依赖（PyMuPDF / paddleocr 运行时需要）
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# 安装到 /install 目录，便于后续复制
RUN pip install --no-cache-dir --prefix=/install -i https://mirrors.tencentyun.com/pypi/simple -r requirements.txt

# ============================================================
# Stage 2: 运行时
# ============================================================
FROM python:${PYTHON_VERSION}-slim-bookworm

WORKDIR /app

# 更换为腾讯云镜像源
RUN sed -i 's/deb.debian.org/mirrors.tencentyun.com/g' /etc/apt/sources.list.d/debian.sources

# 复制系统库依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# 复制已安装的 Python 包
COPY --from=builder /install /usr/local

# 复制应用代码
COPY . .

# 创建上传临时目录
RUN mkdir -p /tmp/kb_uploads

EXPOSE ${UVICORN_PORT}

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health')" || exit 1

# 默认启动 API 服务；Worker 启动时覆盖 CMD
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${UVICORN_PORT:-8000} --workers ${UVICORN_WORKERS:-4}"]