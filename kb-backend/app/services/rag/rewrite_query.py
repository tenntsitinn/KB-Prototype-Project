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
    user_base_url = ""
    user_model = ""

    try:
        if user and state.get("db"):
            from app.core.llm_config import resolve_user_llm_config
            user_api_key, user_base_url, user_model = await resolve_user_llm_config(state["db"], user)
        client = _get_llm_client(user_api_key, user_base_url)
        resp = await client.chat.completions.create(
            model=user_model or settings.LLM_MODEL,
            messages=[{"role": "user", "content": QUERY_REWRITE_PROMPT.format(question=question)}],
            temperature=0.1, max_tokens=256,
        )
        rewritten = resp.choices[0].message.content.strip()
        return {"rewritten_query": rewritten if rewritten else question}
    except Exception:
        return {"rewritten_query": question}