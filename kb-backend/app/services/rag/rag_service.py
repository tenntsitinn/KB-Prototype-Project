"""
RAG 检索问答服务 —— 对外接口 + LLM 生成 + 日志。

图节点业务逻辑已拆分到 services/rag/{node}.py 独立文件。
"""
import time
import json
import uuid
import logging
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.knowledge_unit import QAAccessLog
from app.models.user import User
from app.schemas.rag import SourceInfo, AskResponse
from app.graphs.rag_graph import (
    ChunkResult,
    RAGState,
    _get_llm_client,
    run_rag_graph,
)
from app.prompts.rag_prompts import RAG_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class RagService:
    """RAG 检索问答服务 —— 对外接口 + LLM 生成 + 日志。"""

    async def ask(
        self,
        db: AsyncSession,
        question: str,
        user: User,
        session_id: str | None = None,
        stream: bool = False,
        top_k: int | None = None,
    ) -> AskResponse | AsyncGenerator[str, None]:
        t_start = time.time()
        session_id = session_id or uuid.uuid4().hex[:16]
        user_api_key = user.llm_api_key or "" if not user.is_superuser else ""

        state: RAGState = {
            "question": question, "user": user, "db": db,
            "session_id": session_id, "top_k": top_k or settings.RAG_TOP_K,
        }
        result = await run_rag_graph(state)

        if result.get("faq_cache_hit"):
            if stream:
                return self._cached_streaming(result["faq_cached_answer"], session_id, t_start)
            else:
                return await self._cached_non_streaming(result["faq_cached_answer"], session_id, t_start, db, user)

        chunks: list[ChunkResult] = result.get("final_chunks", [])
        context = result.get("context", "")
        sources_json = result.get("sources_json", "[]")
        context_images: list[str] = result.get("context_images", [])

        if stream:
            return self._ask_streaming(question, context, sources_json, chunks, context_images, session_id, t_start, db, user, user_api_key)
        else:
            return await self._ask_non_streaming(question, context, sources_json, chunks, context_images, session_id, t_start, db, user, user_api_key)

    async def _ask_non_streaming(
        self, question: str, context: str, sources_json: str,
        chunks: list[ChunkResult], context_images: list[str], session_id: str,
        t_start: float, db: AsyncSession, user: User, user_api_key: str = "",
    ) -> AskResponse:
        sources = [SourceInfo(**s) for s in json.loads(sources_json)]
        answer = await self._generate_answer(question, context, user_api_key)
        answer = self._inject_images(answer, context_images)
        response_time_ms = int((time.time() - t_start) * 1000)
        await self._log_access(db, user.id, session_id, question, answer, chunks, response_time_ms)
        return AskResponse(answer=answer, sources=sources, session_id=session_id, response_time_ms=response_time_ms)

    async def _ask_streaming(
        self, question: str, context: str, sources_json: str,
        chunks: list[ChunkResult], context_images: list[str], session_id: str,
        t_start: float, db: AsyncSession, user: User, user_api_key: str = "",
    ) -> AsyncGenerator[str, None]:
        yield f"event: sources\ndata: {sources_json}\n\n"

        full_answer = ""
        async for token in self._generate_answer_stream(question, context, user_api_key):
            full_answer += token
            yield f"event: delta\ndata: {json.dumps({'content': token}, ensure_ascii=False)}\n\n"

        # 注入图片
        image_block = self._build_image_block(context_images)
        if image_block and image_block not in full_answer:
            full_answer += image_block
            yield f"event: delta\ndata: {json.dumps({'content': image_block}, ensure_ascii=False)}\n\n"

        response_time_ms = int((time.time() - t_start) * 1000)
        await self._log_access(db, user.id, session_id, question, full_answer, chunks, response_time_ms)

        done_data = json.dumps({"session_id": session_id, "response_time_ms": response_time_ms}, ensure_ascii=False)
        yield f"event: done\ndata: {done_data}\n\n"

    async def _generate_answer(self, question: str, context: str, user_api_key: str = "") -> str:
        client = _get_llm_client(user_api_key)
        resp = await client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[
                {"role": "system", "content": RAG_SYSTEM_PROMPT.format(context=context)},
                {"role": "user", "content": question},
            ],
            temperature=0.3, max_tokens=2048,
        )
        return resp.choices[0].message.content or ""

    async def _generate_answer_stream(self, question: str, context: str, user_api_key: str = "") -> AsyncGenerator[str, None]:
        client = _get_llm_client(user_api_key)
        stream = await client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[
                {"role": "system", "content": RAG_SYSTEM_PROMPT.format(context=context)},
                {"role": "user", "content": question},
            ],
            temperature=0.3, max_tokens=2048, stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                yield delta.content

    @staticmethod
    def _inject_images(answer: str, context_images: list[str]) -> str:
        """将知识库图片注入到回答末尾"""
        if not context_images:
            return answer
        imgs = "\n".join(context_images)
        return f"{answer}\n\n---\n\n{imgs}"

    @staticmethod
    def _build_image_block(context_images: list[str]) -> str:
        """构建图片注入块"""
        if not context_images:
            return ""
        imgs = "\n".join(context_images)
        return f"\n\n---\n\n{imgs}"

    async def _log_access(
        self, db: AsyncSession, user_id: str, session_id: str,
        question: str, answer: str, chunks: list[ChunkResult], response_time_ms: int,
    ) -> None:
        try:
            recalled_ids = list({c.unit_id for c in chunks})
            log = QAAccessLog(
                session_id=session_id, user_id=user_id,
                question=question, answer=answer,
                recalled_unit_ids_json=json.dumps(recalled_ids, ensure_ascii=False),
                authorized_unit_ids_json=json.dumps(recalled_ids, ensure_ascii=False),
                response_time_ms=response_time_ms,
            )
            db.add(log)
            await db.commit()
        except Exception:
            pass

    async def _cached_non_streaming(
        self, answer: str, session_id: str, t_start: float, db: AsyncSession, user: User,
    ) -> AskResponse:
        response_time_ms = int((time.time() - t_start) * 1000)
        await self._log_access(db, user.id, session_id, "[FAQ缓存命中]", answer, [], response_time_ms)
        return AskResponse(answer=answer, sources=[], session_id=session_id, response_time_ms=response_time_ms)

    async def _cached_streaming(
        self, answer: str, session_id: str, t_start: float,
    ) -> AsyncGenerator[str, None]:
        done = json.dumps(
            {"session_id": session_id, "response_time_ms": int((time.time() - t_start) * 1000)},
            ensure_ascii=False,
        )
        yield "event: sources\ndata: []\n\n"
        yield f"event: delta\ndata: {json.dumps({'content': answer}, ensure_ascii=False)}\n\n"
        yield f"event: done\ndata: {done}\n\n"


rag_service = RagService()