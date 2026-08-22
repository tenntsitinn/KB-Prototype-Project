param(
    [string]$IP = "119.45.220.37"
)

$envContent = @"
# === 自动生成，修改 IP 只需改上方 $IP 变量，然后运行：.\gen-env.ps1 ===

# PostgreSQL
DATABASE_URL=postgresql+asyncpg://kb_user:kb_pass@${IP}:5432/knowledge_base

# Milvus
MILVUS_HOST=${IP}
MILVUS_PORT=19530

# MinIO
MINIO_ENDPOINT=${IP}:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET_DOCS=kb-documents

# Redis / Celery
REDIS_URL=redis://${IP}:6379/0

# Embedding (BGE_M3)
EMBEDDING_API_KEY=sk-igxppoqfzyveitzpafxezmzndrqfpolmzxhxlyingkfkewfy
EMBEDDING_BASE_URL=https://api.siliconflow.cn/v1
EMBEDDING_MODEL=BAAI/bge-m3
EMBEDDING_DIM=1024

# LLM (DeepSeek)
LLM_BASE_URL=https://api.deepseek.com
LLM_API_KEY=sk-1a3c50caee894b8e92b7372f3293832f
LLM_MODEL=deepseek-v4-flash

# Vision (Qwen-VL)
VISION_MODEL=qwen-vl-max
VISION_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
VISION_API_KEY=sk-b87415bf3d4d4b5393dee3817b893344

# Rerank (SiliconFlow)
RERANK_MODEL=BAAI/bge-reranker-v2-m3
RERANK_BASE_URL=https://api.siliconflow.cn/v1
RERANK_API_KEY=sk-igxppoqfzyveitzpafxezmzndrqfpolmzxhxlyingkfkewfy

# Upload
UPLOAD_TEMP_DIR=./tmp/kb_uploads

# OCR（本地调试关闭）
USE_UNLIMITED_OCR=false
UNLIMITED_OCR_URL=

# JWT
JWT_SECRET_KEY=change-me-in-production
"@

$envContent | Out-File -FilePath "$PSScriptRoot\.env" -Encoding utf8
Write-Host ".env 已生成，IP = $IP" -ForegroundColor Green