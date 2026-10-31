"""Step 4: turn text into vectors.

GeminiEmbedder - Gemini embedding API (same key as the LLM).
TfidfEmbedder  - offline fallback, no network or key; fitted on the corpus and saved with the index.
Vectors are L2-normalised, so cosine similarity = dot product.
"""
from __future__ import annotations

import logging
import pickle
import time
from pathlib import Path
from typing import Protocol

import numpy as np
import openai

from agent.llm.client import RETRYABLE_ERRORS

logger = logging.getLogger(__name__)
TFIDF_STATE_FILE = "tfidf.pkl"


def normalize(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors / np.where(norms == 0, 1, norms)


class Embedder(Protocol):
    provider: str
    model: str

    def fit(self, texts: list[str]) -> None: ...
    def embed(self, texts: list[str]) -> np.ndarray: ...
    def save(self, index_dir: Path) -> None: ...


class GeminiEmbedder:
    provider = "gemini"

    def __init__(self, model: str, api_key: str, base_url: str, batch_size: int, max_retries: int,
                 backoff_s: float, client=None):
        self.model = model
        self.batch_size = batch_size
        self.max_retries = max_retries
        self.backoff_s = backoff_s
        self._client = client or openai.OpenAI(api_key=api_key, base_url=base_url)

    def fit(self, texts: list[str]) -> None:
        """Nothing to fit: the model is pretrained."""

    def embed(self, texts: list[str]) -> np.ndarray:
        rows = []
        for start in range(0, len(texts), self.batch_size):
            batch = texts[start:start + self.batch_size]
            rows.extend(self._embed_batch(batch))
        return normalize(np.asarray(rows, dtype=np.float32))

    def save(self, index_dir: Path) -> None:
        """Nothing to save."""

    def _embed_batch(self, batch: list[str]) -> list[list[float]]:
        for attempt in range(self.max_retries + 1):
            t = time.perf_counter()
            try:
                resp = self._client.embeddings.create(model=self.model, input=batch)
                logger.debug("Embedded %d texts in %.2fs", len(batch), time.perf_counter() - t)
                return [d.embedding for d in resp.data]
            except RETRYABLE_ERRORS as e:
                if attempt == self.max_retries:
                    raise
                wait = self.backoff_s * 2 ** attempt
                logger.warning("Embedding request failed (%s). Retry in %.0fs.", type(e).__name__, wait)
                time.sleep(wait)
        raise RuntimeError("unreachable")


class TfidfEmbedder:
    provider = "tfidf"
    model = "tfidf-1-2gram"

    def __init__(self, vectorizer=None):
        from sklearn.feature_extraction.text import TfidfVectorizer
        self._vec = vectorizer or TfidfVectorizer(ngram_range=(1, 2), stop_words="english", sublinear_tf=True)

    def fit(self, texts: list[str]) -> None:
        self._vec.fit(texts)

    def embed(self, texts: list[str]) -> np.ndarray:
        return normalize(self._vec.transform(texts).toarray().astype(np.float32))

    def save(self, index_dir: Path) -> None:
        with open(index_dir / TFIDF_STATE_FILE, "wb") as f:
            pickle.dump(self._vec, f)

    @classmethod
    def load(cls, index_dir: Path) -> "TfidfEmbedder":
        # The file is produced by our own build_index script, never by external input.
        with open(index_dir / TFIDF_STATE_FILE, "rb") as f:
            return cls(pickle.load(f))
