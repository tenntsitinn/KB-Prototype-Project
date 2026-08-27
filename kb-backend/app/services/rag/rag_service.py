"""
RAG 检索问答服务 —— 对外接口 + LLM 生成 + 日志。

图节点业务逻辑已拆分到 services/rag/{node}.py 独立文件。
"""
import time
import json
import re
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

# 末尾未闭合的残缺图片引用（流式截断时遗留），用于答案侧清理
_PARTIAL_IMAGE_TAIL_RE = re.compile(r"!\[[^\]\n]*(?:\]\([^)\n]*)?$")


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
        chapter_id: str | None = None,
    ) -> AskResponse | AsyncGenerator[str, None]:
        t_start = time.time()
        session_id = session_id or uuid.uuid4().hex[:16]
        from app.core.llm_config import resolve_user_llm_config
        user_api_key, user_base_url, user_model = resolve_user_llm_config(user)

        state: RAGState = {
            "question": question, "user": user, "db": db,
            "session_id": session_id, "top_k": top_k or settings.RAG_TOP_K,
        }
        if chapter_id:
            state["scope_chapter_id"] = chapter_id
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
            return self._ask_streaming(question, context, sources_json, chunks, context_images, session_id, t_start, db, user, user_api_key, user_base_url, user_model)
        else:
            return await self._ask_non_streaming(question, context, sources_json, chunks, context_images, session_id, t_start, db, user, user_api_key, user_base_url, user_model)

    async def _ask_non_streaming(
        self, question: str, context: str, sources_json: str,
        chunks: list[ChunkResult], context_images: list[str], session_id: str,
        t_start: float, db: AsyncSession, user: User, user_api_key: str = "",
        user_base_url: str = "", user_model: str = "",
    ) -> AskResponse:
        sources = [SourceInfo(**s) for s in json.loads(sources_json)]
        answer = await self._generate_answer(question, context, user_api_key, user_base_url, user_model)
        answer = self._inject_images(answer, context_images)
        response_time_ms = int((time.time() - t_start) * 1000)
        await self._log_access(db, user.id, session_id, question, answer, chunks, response_time_ms)
        return AskResponse(answer=answer, sources=sources, session_id=session_id, response_time_ms=response_time_ms)

    async def _ask_streaming(
        self, question: str, context: str, sources_json: str,
        chunks: list[ChunkResult], context_images: list[str], session_id: str,
        t_start: float, db: AsyncSession, user: User, user_api_key: str = "",
        user_base_url: str = "", user_model: str = "",
    ) -> AsyncGenerator[str, None]:
        yield f"event: sources\ndata: {sources_json}\n\n"

        full_answer = ""
        buffer = ""
        async for token in self._generate_answer_stream(question, context, user_api_key, user_base_url, user_model):
            buffer += token
            # 缓冲开头疑似图片引用的内容，避免 LLM 复述的图片流给前端
            emitted, buffer = self._drain_image_buffer(buffer)
            if emitted:
                full_answer += emitted
                yield f"event: delta\ndata: {json.dumps({'content': emitted}, ensure_ascii=False)}\n\n"
        # 流结束：处理残余缓冲（末尾图片引用剥离；普通文本放行）
        tail = self._strip_image_refs(buffer)
        if tail:
            full_answer += tail
            yield f"event: delta\ndata: {json.dumps({'content': tail}, ensure_ascii=False)}\n\n"

        # 注入图片
        image_block = self._build_image_block(context_images)
        if image_block and image_block not in full_answer:
            full_answer += image_block
            yield f"event: delta\ndata: {json.dumps({'content': image_block}, ensure_ascii=False)}\n\n"

        response_time_ms = int((time.time() - t_start) * 1000)
        await self._log_access(db, user.id, session_id, question, full_answer, chunks, response_time_ms)

        done_data = json.dumps({"session_id": session_id, "response_time_ms": response_time_ms}, ensure_ascii=False)
        yield f"event: done\ndata: {done_data}\n\n"

    async def _generate_answer(self, question: str, context: str, user_api_key: str = "", user_base_url: str = "", user_model: str = "") -> str:
        client = _get_llm_client(user_api_key, user_base_url)
        try:
            resp = await client.chat.completions.create(
                model=user_model or settings.LLM_MODEL,
                messages=[
                    {"role": "system", "content": RAG_SYSTEM_PROMPT.format(context=context)},
                    {"role": "user", "content": question},
                ],
                temperature=0.3, max_tokens=2048,
            )
            if not resp.choices:
                return "抱歉，生成服务返回了空结果，请稍后重试。"
            return resp.choices[0].message.content or ""
        except Exception as e:
            logger.error(f"LLM 生成失败: {e}", exc_info=True)
            return f"抱歉，生成回答时出错：{e}。请检查 API Key 配置或稍后重试。"

    async def _generate_answer_stream(self, question: str, context: str, user_api_key: str = "", user_base_url: str = "", user_model: str = "") -> AsyncGenerator[str, None]:
        client = _get_llm_client(user_api_key, user_base_url)
        try:
            stream = await client.chat.completions.create(
                model=user_model or settings.LLM_MODEL,
                messages=[
                    {"role": "system", "content": RAG_SYSTEM_PROMPT.format(context=context)},
                    {"role": "user", "content": question},
                ],
                temperature=0.3, max_tokens=2048, stream=True,
            )
            async for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    yield delta.content
        except Exception as e:
            logger.error(f"LLM 流式生成失败: {e}", exc_info=True)
            yield f"\n\n抱歉，生成回答时出错：{e}。请检查 API Key 配置或稍后重试。"

    @staticmethod
    def _strip_image_refs(answer: str) -> str:
        """剥离 LLM 回答中复述的图片引用，图片统一由末尾注入。

        同时剥离末尾未闭合的残缺引用（流被 max_tokens 截断时的 ![...(）。
        """
        text = re.sub(r"!\[.*?\]\([^)]+\)\s*", "", answer)
        return _PARTIAL_IMAGE_TAIL_RE.sub("", text)

    @staticmethod
    def _drain_image_buffer(buffer: str) -> tuple[str, str]:
        """流式缓冲排水：完整的非图片前缀立即放行，疑似图片引用的部分留在缓冲。

        返回 (放行文本, 剩余缓冲)。图片引用只在缓冲内完整成形后被丢弃，
        避免流式 token 把 ![...](...) 切碎后漏到前端。
        """
        emitted = ""
        while buffer:
            idx = buffer.find("![")
            if idx == -1:
                # 尾部暂留一个 "!"：它可能是下一 token 里 "![...](...)" 的开头
                cut = len(buffer) - (1 if buffer.endswith("!") else 0)
                emitted += buffer[:cut]
                buffer = buffer[cut:]
                break
            emitted += buffer[:idx]
            buffer = buffer[idx:]
            close = buffer.find(")")
            if close == -1:
                # 还没收尾：要么是跨 token 的图片引用，要么文本里恰好出现 "!["
                # 图片引用 URL 不会太长，超过阈值判为普通文本放行
                if len(buffer) > 2048:
                    emitted += buffer[:2]
                    buffer = buffer[2:]
                    continue
                break
            # 成形一个候选引用：校验形状 ![...](...) 才丢弃，否则当作普通文本
            candidate = buffer[: close + 1]
            if re.fullmatch(r"!\[[^\[\]]*\]\([^()]*\)", candidate):
                buffer = buffer[close + 1:]
            else:
                emitted += buffer[:2]
                buffer = buffer[2:]
        return emitted, buffer

    @staticmethod
    def _inject_images(answer: str, context_images: list[str]) -> str:
        """将知识库图片注入到回答末尾（先剥离回答中复述的引用，图片只走这一个通道）"""
        answer = RagService._strip_image_refs(answer)
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