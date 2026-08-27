import os
from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from contextlib import asynccontextmanager
from starlette.middleware.base import BaseHTTPMiddleware
from app.api.knowledge import router as knowledge_router
from app.api.auth import router as auth_router
from app.api.users import router as users_router
from app.api.roles import router as roles_router
from app.api.departments import router as departments_router
from app.api.rag import router as rag_router
from app.api.gap import router as gap_router
from app.api.dashboard import router as dashboard_router
from app.api.tags import router as tags_router
from app.api.quiz import router as quiz_router
from app.api.education import router as education_router
from app.core.database import AsyncSessionLocal
from app.services.rag import faq_service

# 最大请求体 = 100MB 文件 + multipart 开销（DOCX 超过 50MB 会在 worker 中流式自动拆分）
MAX_REQUEST_BODY = 120 * 1024 * 1024  # 120MB


class MaxBodySizeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        cl = request.headers.get("content-length")
        if cl and int(cl) > MAX_REQUEST_BODY:
            return JSONResponse(
                status_code=413,
                content={"detail": f"请求体超过最大限制 {MAX_REQUEST_BODY // (1024 * 1024)}MB"},
            )
        return await call_next(request)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with AsyncSessionLocal() as db:
        await faq_service.sync_faq_cache(db)
    yield


app = FastAPI(title="知识库管理平台", version="0.1.0", lifespan=lifespan)
app.add_middleware(MaxBodySizeMiddleware)

app.include_router(knowledge_router)
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(roles_router)
app.include_router(departments_router)
app.include_router(rag_router)
app.include_router(gap_router)
app.include_router(dashboard_router)
app.include_router(tags_router)
app.include_router(quiz_router)
app.include_router(education_router)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/{full_path:path}")
async def serve_frontend(full_path: str):
    """SPA fallback: serve static files or index.html"""
    dist_dir = "app/static/dist"
    file_path = os.path.join(dist_dir, full_path)
    headers = {"Cache-Control": "no-cache, no-store, must-revalidate"}
    if full_path and os.path.isfile(file_path):
        return FileResponse(file_path, headers=headers)
    return FileResponse(os.path.join(dist_dir, "index.html"), headers=headers)
