"""Deterministic substitutes for paid model providers."""

from __future__ import annotations

import hashlib
from types import SimpleNamespace
from typing import Any


class FakeEmbedding:
    """Return stable, normalized vectors without loading a model."""

    def __init__(self, dimension: int = 8) -> None:
        self.dimension = dimension
        self.calls: list[list[str]] = []

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        return [self._vector(text) for text in texts]

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return await self.embed(texts)

    def _vector(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        values = [digest[i] / 255.0 for i in range(self.dimension)]
        norm = sum(value * value for value in values) ** 0.5 or 1.0
        return [value / norm for value in values]


class _FakeCompletions:
    def __init__(self, owner: "FakeLLM") -> None:
        self.owner = owner

    async def create(self, **kwargs: Any) -> SimpleNamespace:
        self.owner.calls.append(kwargs)
        content = self.owner.responses.pop(0) if self.owner.responses else self.owner.default_response
        message = SimpleNamespace(content=content)
        choice = SimpleNamespace(message=message, delta=message)
        return SimpleNamespace(choices=[choice])


class FakeLLM:
    """Small AsyncOpenAI-compatible chat client."""

    def __init__(self, responses: list[str] | None = None, default_response: str = "fake answer") -> None:
        self.responses = list(responses or [])
        self.default_response = default_response
        self.calls: list[dict[str, Any]] = []
        self.chat = SimpleNamespace(completions=_FakeCompletions(self))


class FakeRerank:
    """Rank documents deterministically by query-term overlap."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def rerank(self, query: str, documents: list[str], top_n: int | None = None) -> list[dict[str, float | int]]:
        self.calls.append({"query": query, "documents": list(documents), "top_n": top_n})
        terms = {term for term in query.lower().split() if term}
        scored = []
        for index, document in enumerate(documents):
            lowered = document.lower()
            score = float(sum(term in lowered for term in terms))
            scored.append({"index": index, "relevance_score": score})
        scored.sort(key=lambda item: (-float(item["relevance_score"]), int(item["index"])))
        return scored[: top_n or len(scored)]
