"""Step 4: turn text into vectors.

GeminiEmbedder - Gemini embedding API (same key as the LLM).
TfidfEmbedder  - offline fallback, no network or key; fitted on the corpus and saved with the index.
Vectors are L2-normalised, so cosine similarity = dot product.
"""
from __future__ import annotations

import logging
import pickle
import re
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np
import openai

from agent.llm.client import RETRYABLE_ERRORS

logger = logging.getLogger(__name__)
TFIDF_STATE_FILE = "tfidf.pkl"
_RETRY_IN = re.compile(r"retry in ([0-9.]+)s", re.I)


@dataclass(frozen=True)
class RateLimit:
    texts_per_minute: int
    max_retries: int
    wait_s: float


class TextThrottle:
    """Sliding one-minute window: blocks until sending `n` more texts keeps us under the limit."""

    def __init__(self, per_minute: int, clock=time.monotonic, sleep=time.sleep):
        self.per_minute, self._clock, self._sleep = per_minute, clock, sleep
        self._sent: deque[tuple[float, int]] = deque()

    def acquire(self, n: int) -> None:
        while True:
            now = self._clock()
            while self._sent and now - self._sent[0][0] >= 60:
                self._sent.popleft()
            used = sum(k for _, k in self._sent)
            if used + n <= self.per_minute or not self._sent:
                self._sent.append((now, n))
                return
            wait = 60 - (now - self._sent[0][0]) + 0.5
            logger.info("Embedding rate limit: waiting %.0fs (%d texts in the last minute)", wait, used)
            self._sleep(wait)


def retry_after_s(error: Exception, default: float) -> float:
    m = _RETRY_IN.search(str(error))
    return float(m.group(1)) + 1 if m else default


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
                 backoff_s: float, rate_limit: RateLimit, client=None, sleep=time.sleep):
        self.model = model
        self.batch_size = min(batch_size, rate_limit.texts_per_minute)
        self.max_retries = max_retries
        self.backoff_s = backoff_s
        self.rate_limit = rate_limit
        self._throttle = TextThrottle(rate_limit.texts_per_minute, sleep=sleep)
        self._sleep = sleep
        self._client = client or openai.OpenAI(api_key=api_key, base_url=base_url)

    def fit(self, texts: list[str]) -> None:
        """Nothing to fit: the model is pretrained."""

    def embed(self, texts: list[str]) -> np.ndarray:
        rows = []
        for start in range(0, len(texts), self.batch_size):
            batch = texts[start:start + self.batch_size]
            self._throttle.acquire(len(batch))
            rows.extend(self._embed_batch(batch))
            if len(texts) > self.batch_size:
                logger.info("Embedded %d/%d texts", min(start + self.batch_size, len(texts)), len(texts))
        return normalize(np.asarray(rows, dtype=np.float32))

    def save(self, index_dir: Path) -> None:
        """Nothing to save."""

    def _embed_batch(self, batch: list[str]) -> list[list[float]]:
        errors = rate_limited = 0
        while True:
            t = time.perf_counter()
            try:
                resp = self._client.embeddings.create(model=self.model, input=batch)
                logger.debug("Embedded %d texts in %.2fs", len(batch), time.perf_counter() - t)
                return [d.embedding for d in resp.data]
            except openai.RateLimitError as e:
                rate_limited += 1
                if rate_limited > self.rate_limit.max_retries:
                    raise
                wait = retry_after_s(e, self.rate_limit.wait_s)
                logger.warning("Embedding quota hit (429). Waiting %.0fs as the API asks (%d/%d).",
                               wait, rate_limited, self.rate_limit.max_retries)
                self._sleep(wait)
            except RETRYABLE_ERRORS as e:
                errors += 1
                if errors > self.max_retries:
                    raise
                wait = self.backoff_s * 2 ** (errors - 1)
                logger.warning("Embedding request failed (%s). Retry in %.0fs.", type(e).__name__, wait)
                self._sleep(wait)


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
