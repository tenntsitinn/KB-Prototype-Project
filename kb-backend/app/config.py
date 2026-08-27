import sys

from pydantic_settings import BaseSettings

_DEFAULT_JWT_SECRET = "change-me-in-production"
_DEFAULT_MINIO_KEY = "minioadmin"


class Settings(BaseSettings):
    # 运行环境: development | production
    APP_ENV: str = "development"

    # 产品模式: education | personal
    APP_MODE: str = "education"

    # PostgreSQL
    DATABASE_URL: str = "postgresql+asyncpg://kb_user:kb_pass@localhost:5432/knowledge_base"

    # Milvus
    MILVUS_HOST: str = "localhost"
    MILVUS_PORT: int = 19530
    MILVUS_LITE_DB: str = ""  # 非空时使用 milvus-lite (如: "milvus.db")
    MILVUS_COLLECTION: str = "knowledge_units"

    # MinIO
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = _DEFAULT_MINIO_KEY
    MINIO_SECRET_KEY: str = _DEFAULT_MINIO_KEY
    MINIO_BUCKET_DOCS: str = "kb-documents"
    MINIO_SECURE: bool = False
    MINIO_EXTERNAL_ENDPOINT: str = ""  # 浏览器可达地址（如 http://129.204.52.161:9000），空时回退 MINIO_ENDPOINT

    # Redis / Celery
    REDIS_URL: str = "redis://localhost:6379/0"

    # File size limits (MB)
    MAX_SIZE_PDF: int = 20
    MAX_SIZE_DOCX: int = 50
    MAX_SIZE_MD: int = 5
    MAX_SIZE_TXT: int = 5

    # PDF split
    PDF_SPLIT_BUFFER: float = 0.9

    # DOCX split（流式拆分时的未压缩 XML 大小倍数，XML 压缩比通常 3~5x）
    DOCX_SPLIT_BUFFER: float = 3.0

    # Chunking
    # overlap 曾设为 0 以缓解图片重复召回；现已在 RAG 层按 URL 去重并在答案侧
    # 剥离复述引用（build_context.py / rag_service.py），边界召回收益恢复，故恢复重叠
    CHUNK_SIZE: int = 800
    CHUNK_OVERLAP: int = 120

    # Embedding
    EMBEDDING_LOCAL: bool = False  # True=本地 sentence-transformers, False=远程 API
    EMBEDDING_MODEL: str = "BAAI/bge-m3"
    EMBEDDING_MODEL_DIR: str = "/app/models"  # 本地模型缓存目录
    EMBEDDING_DIM: int = 1024
    EMBEDDING_API_KEY: str = ""
    EMBEDDING_BASE_URL: str = "https://api.siliconflow.cn/v1"

    # Soft delete
    SOFT_DELETE_DAYS: int = 7

    # Unlimited-OCR (百度 VLM 模型，统一处理所有类型 PDF)
    USE_UNLIMITED_OCR: bool = False
    UNLIMITED_OCR_URL: str = ""  # 非空时走远程 OCR 服务，空时本地加载模型

    # Upload temp dir
    UPLOAD_TEMP_DIR: str = "/tmp/kb_uploads"

    # LLM (用于 HyDE / 问题重写 / 最终生成)
    LLM_BASE_URL: str = "https://api.deepseek.com"
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "deepseek-v4-flash"

    # Vision (用于 markdown 图片描述生成)
    VISION_MODEL: str = "qwen-vl-max"
    VISION_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    VISION_API_KEY: str = ""

    # Rerank
    RERANK_MODEL: str = "BAAI/bge-reranker-v2-m3"
    RERANK_BASE_URL: str = "https://api.siliconflow.cn/v1"
    RERANK_API_KEY: str = ""

    # RAG 参数
    RAG_TOP_K: int = 10
    RAG_RECALL_MULTIPLIER: int = 5
    RAG_RECALL_MULTIPLIER_FALLBACK: int = 10
    RAG_SIMILARITY_THRESHOLD: float = 0.5
    RAG_SIMILARITY_THRESHOLD_FALLBACK: float = 0.4
    RAG_RRF_K: int = 60

    # FAQ 挖掘与缓存
    FAQ_MINING_DAYS: int = 30
    FAQ_MINING_THRESHOLD: int = 3
    FAQ_CACHE_COLLECTION: str = "faq_cache"
    FAQ_CACHE_THRESHOLD: float = 0.92
    FAQ_CLUSTER_THRESHOLD: float = 0.88

    # 知识缺口
    GAP_SCORE_THRESHOLD: float = 0.5

    # 知识点提取
    POINT_REWRITE_INTERVAL: int = 20          # 每处理多少 chunk 触发一次批量重写落库
    TOPIC_MATCH_THRESHOLD: float = 0.7        # topic 相似度 > 该值：自动合并进已有知识点
    TOPIC_CANDIDATE_THRESHOLD: float = 0.5    # 介于两阈值之间：新建并记录合并候选，人工审核
    MILVUS_TOPIC_COLLECTION: str = "knowledge_topics"

    # 用户 API Key 加密密钥（留空时从 JWT_SECRET_KEY 派生）
    ENCRYPTION_KEY: str = ""

    # JWT
    JWT_SECRET_KEY: str = _DEFAULT_JWT_SECRET
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # 8 hours
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    class Config:
        env_file = ".env"


settings = Settings()


def _check_production_security(s: Settings) -> list[str]:
    if s.APP_ENV != "production":
        return []
    failures: list[str] = []
    if s.JWT_SECRET_KEY == _DEFAULT_JWT_SECRET:
        failures.append("JWT_SECRET_KEY is still the default value")
    if len(s.JWT_SECRET_KEY) < 32:
        failures.append("JWT_SECRET_KEY must be at least 32 bytes in production")
    if s.MINIO_SECRET_KEY == _DEFAULT_MINIO_KEY:
        failures.append("MINIO_SECRET_KEY is still the default value")
    return failures


_failures = _check_production_security(settings)
if _failures:
    print("FATAL: production security check failed:", file=sys.stderr)
    for f in _failures:
        print(f"  - {f}", file=sys.stderr)
    sys.exit(1)