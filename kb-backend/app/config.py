from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # PostgreSQL
    DATABASE_URL: str = "postgresql+asyncpg://kb_user:kb_pass@localhost:5432/knowledge_base"

    # Milvus
    MILVUS_HOST: str = "localhost"
    MILVUS_PORT: int = 19530
    MILVUS_LITE_DB: str = ""  # 非空时使用 milvus-lite (如: "milvus.db")
    MILVUS_COLLECTION: str = "knowledge_units"

    # MinIO
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET_DOCS: str = "kb-documents"
    MINIO_SECURE: bool = False

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
    CHUNK_SIZE: int = 800
    CHUNK_OVERLAP: int = 0

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

    # 知识缺口
    GAP_SCORE_THRESHOLD: float = 0.5

    # JWT
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # 8 hours
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    class Config:
        env_file = ".env"


settings = Settings()