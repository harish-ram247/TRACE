"""Text embedding behind a small interface, so tests and CI never download a model."""

from __future__ import annotations

import hashlib
import re
from functools import lru_cache
from typing import Protocol

import numpy as np

from app.core.config import get_settings
from app.core.tls import use_system_trust_store


class Embedder(Protocol):
    name: str
    dim: int

    def embed_passages(self, texts: list[str]) -> list[np.ndarray]: ...

    def embed_query(self, text: str) -> np.ndarray: ...


def passage_text(section_path: str, text: str) -> str:
    """What gets embedded for a chunk: the heading trail adds context the body often lacks."""
    return f"{section_path}\n\n{text}"


class FastEmbedder:
    """ONNX embedding via fastembed (no PyTorch). Downloads the model on first use."""

    def __init__(
        self,
        model_name: str,
        query_prefix: str = "",
        cache_dir: str | None = None,
        batch_size: int = 32,
    ):
        from fastembed import TextEmbedding

        use_system_trust_store()
        self._model = TextEmbedding(model_name=model_name, cache_dir=cache_dir)
        self.name = model_name
        self.query_prefix = query_prefix
        self.batch_size = batch_size
        self.dim = len(next(iter(self._model.embed(["probe"]))))

    def embed_passages(self, texts: list[str]) -> list[np.ndarray]:
        return [np.asarray(v, dtype=np.float32) for v in self._model.embed(texts, self.batch_size)]

    def embed_query(self, text: str) -> np.ndarray:
        vec = next(iter(self._model.embed([self.query_prefix + text])))
        return np.asarray(vec, dtype=np.float32)


class HashEmbedder:
    """Deterministic bag-of-words hashing embedder for tests and offline development.

    Texts that share words get similar vectors. It is not a semantic model.
    """

    _TOKEN = re.compile(r"[a-z0-9]+")

    def __init__(self, dim: int = 384):
        self.name = f"hash-bow-{dim}"
        self.dim = dim

    def _vector(self, text: str) -> np.ndarray:
        vec = np.zeros(self.dim, dtype=np.float32)
        for token in self._TOKEN.findall(text.lower()):
            digest = hashlib.md5(token.encode(), usedforsecurity=False).digest()
            vec[int.from_bytes(digest[:4], "little") % self.dim] += 1.0
        vec[0] += 1e-3  # never a zero vector: cosine distance to it is undefined
        return vec / np.linalg.norm(vec)

    def embed_passages(self, texts: list[str]) -> list[np.ndarray]:
        return [self._vector(t) for t in texts]

    def embed_query(self, text: str) -> np.ndarray:
        return self._vector(text)


@lru_cache
def get_embedder() -> FastEmbedder:
    s = get_settings()
    return FastEmbedder(s.embedding_model, s.embedding_query_prefix, s.model_cache_dir)
