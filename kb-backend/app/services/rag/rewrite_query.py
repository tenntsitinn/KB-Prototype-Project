"""问题重写"""
import logging
from app.config import settings
from app.graphs.rag_graph import RAGState, _get_llm_client
from app.prompts.rag_prompts import QUERY_REWRITE_PROMPT

logger = logging.getLogger(__name__)


async def do_rewrite_query(state: RAGState) -> dict:
    question = state["question"]
    if len(question) <= 10 and "\n" not in question:
        return {"rewritten_query": question}

    user = state.get("user")
    user_api_key = ""
    if user and not user.is_superuser:
        user_api_key = user.llm_api_key or ""

    try:
        client = _get_llm_client(user_api_key)
        resp = await client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[{"role": "user", "content": QUERY_REWRITE_PROMPT.format(question=question)}],
            temperature=0.1, max_tokens=256,
        )
        rewritten = resp.choices[0].message.content.strip()
        return {"rewritten_query": rewritten if rewritten else question}
    except Exception:
        return {"rewritten_query": question}