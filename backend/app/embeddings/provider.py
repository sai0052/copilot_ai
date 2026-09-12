"""Optional embedding providers for semantic code search."""

from __future__ import annotations

import json
import math
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterable


class EmbeddingProvider(ABC):
    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError


class HashEmbeddingProvider(EmbeddingProvider):
    """Deterministic local fallback so semantic search can run without extra models."""

    def __init__(self, dims: int = 64) -> None:
        self.dims = dims

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            vec = [0.0] * self.dims
            tokens = text.lower().split()
            for token in tokens:
                idx = hash(token) % self.dims
                vec[idx] += 1.0
            norm = math.sqrt(sum(v * v for v in vec)) or 1.0
            vectors.append([v / norm for v in vec])
        return vectors


class SentenceTransformerProvider(EmbeddingProvider):
    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self._model = None

    def embed(self, texts: list[str]) -> list[list[float]]:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError("sentence-transformers is not installed") from exc
        if self._model is None:
            self._model = SentenceTransformer(self.model_name)
        vectors = self._model.encode(texts, convert_to_numpy=True)
        return [row.tolist() for row in vectors]


class LocalEmbeddingStore:
    def __init__(self, root: Path, provider: EmbeddingProvider) -> None:
        self.root = root
        self.provider = provider
        self.path = root / ".embeddings" / "index.json"

    def build(self, files: Iterable[tuple[str, str]]) -> None:
        items = list(files)
        vectors = self.provider.embed([content[:4000] for _, content in items])
        payload = [{"path": path, "vector": vector} for (path, _content), vector in zip(items, vectors, strict=True)]
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload), encoding="utf-8")

    def search(self, query: str, top_k: int = 8) -> list[dict]:
        if not self.path.exists():
            return []
        data = json.loads(self.path.read_text(encoding="utf-8"))
        query_vec = self.provider.embed([query])[0]
        scored = []
        for item in data:
            scored.append({"path": item["path"], "score": _cosine(query_vec, item["vector"])})
        scored.sort(key=lambda row: row["score"], reverse=True)
        return scored[:top_k]


def get_embedding_provider(name: str, model: str) -> EmbeddingProvider:
    if name == "sentence_transformers":
        try:
            return SentenceTransformerProvider(model)
        except Exception:
            return HashEmbeddingProvider()
    return HashEmbeddingProvider()


def _cosine(a: list[float], b: list[float]) -> float:
    length = min(len(a), len(b))
    dot = sum(a[i] * b[i] for i in range(length))
    na = math.sqrt(sum(x * x for x in a[:length])) or 1.0
    nb = math.sqrt(sum(x * x for x in b[:length])) or 1.0
    return dot / (na * nb)
