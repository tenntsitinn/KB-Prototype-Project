"""
Celery 异步任务：RAG 批量问答处理。

用于离线批量评估知识库覆盖度、批量生成 FAQ 答案等场景。
线上实时问答走 API 同步调用 rag_service，不经过此任务。
"""
import asyncio
from celery import Celery
from app.config import settings
from app.core.database import AsyncSessionLocal
from app.services.rag.rag_service import rag_service

celery_app = Celery("kb_rag", broker=settings.REDIS_URL, backend=settings.REDIS_URL)


def _run_async(coro):
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(coro)


@celery_app.task(name="rag.batch_evaluate")
def batch_evaluate(questions: list[str], user_id: str) -> dict:
    """
    批量评估知识库覆盖度：对一组问题逐一执行 RAG 检索（不生成回答），
    统计每个问题的召回分数和命中情况。

    参数:
        questions: 待评估的问题列表
        user_id: 模拟用户 ID（用于权限过滤）

    返回:
        {"total": int, "results": [{"question": str, "score": float, "chunk_count": int}, ...]}
    """
    from app.models.user import User

    async def _evaluate():
        mock_user = User(id=user_id, is_superuser=True, department_id="")

        results = []
        async with AsyncSessionLocal() as db:
            for q in questions:
                try:
                    chunks = await rag_service._recall_with_fallback(db, q, mock_user)
                    all_chunks = [c for sublist in chunks for c in sublist]
                    max_score = max((c.score for c in all_chunks), default=0)
                    results.append({
                        "question": q,
                        "score": round(max_score, 4),
                        "chunk_count": len(all_chunks),
                    })
                except Exception:
                    results.append({"question": q, "score": 0, "chunk_count": 0})

        return {"total": len(results), "results": results}

    return _run_async(_evaluate())


@celery_app.task(name="rag.batch_ask")
def batch_ask(questions: list[str], user_id: str) -> dict:
    """
    批量问答：对一组问题执行完整 RAG 流程，返回每个问题的答案。

    参数:
        questions: 问题列表
        user_id: 用户 ID

    返回:
        {"total": int, "answers": [{"question": str, "answer": str, "sources": list}, ...]}
    """
    from app.models.user import User

    async def _batch():
        mock_user = User(id=user_id, is_superuser=True, department_id="")

        answers = []
        async with AsyncSessionLocal() as db:
            for q in questions:
                try:
                    resp = await rag_service.ask(db=db, question=q, user=mock_user, stream=False)
                    answers.append({
                        "question": q,
                        "answer": resp.answer,
                        "sources": [s.model_dump() for s in resp.sources],
                    })
                except Exception as e:
                    answers.append({"question": q, "answer": "", "sources": [], "error": str(e)})

        return {"total": len(answers), "answers": answers}

    return _run_async(_batch())