"""Step 5: store chunk vectors + metadata and search them (top-k with metadata filters).

~250 chunks fit easily in memory: a numpy matrix is simpler and more transparent than a vector database.
Files in index_dir: vectors.npy, chunks.jsonl, manifest.json.
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from agent.rag.models import Chunk

logger = logging.getLogger(__name__)

VECTORS_FILE, CHUNKS_FILE, MANIFEST_FILE = "vectors.npy", "chunks.jsonl", "manifest.json"


class VectorIndex:
    def __init__(self, chunks: list[Chunk], vectors: np.ndarray, manifest: dict):
        if len(chunks) != len(vectors):
            raise ValueError("chunks and vectors have different lengths")
        self.chunks = chunks
        self.vectors = vectors
        self.manifest = manifest

    @classmethod
    def build(cls, chunks: list[Chunk], vectors: np.ndarray, provider: str, model: str) -> "VectorIndex":
        manifest = {"embedding_provider": provider, "embedding_model": model, "dim": int(vectors.shape[1]),
                    "chunks": len(chunks), "policy_chunks": sum(c.source == "policy" for c in chunks),
                    "case_chunks": sum(c.source == "case" for c in chunks),
                    "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        return cls(chunks, vectors, manifest)

    def save(self, index_dir: Path) -> None:
        index_dir.mkdir(parents=True, exist_ok=True)
        np.save(index_dir / VECTORS_FILE, self.vectors)
        with open(index_dir / CHUNKS_FILE, "w", encoding="utf-8") as f:
            for c in self.chunks:
                f.write(json.dumps(asdict(c), ensure_ascii=False) + "\n")
        (index_dir / MANIFEST_FILE).write_text(json.dumps(self.manifest, indent=2), encoding="utf-8")
        logger.info("Index saved to %s: %s", index_dir, self.manifest)

    @classmethod
    def load(cls, index_dir: Path) -> "VectorIndex":
        if not (index_dir / MANIFEST_FILE).is_file():
            raise FileNotFoundError(f"No RAG index in {index_dir}. Run: python -m agent.scripts.build_index")
        manifest = json.loads((index_dir / MANIFEST_FILE).read_text(encoding="utf-8"))
        vectors = np.load(index_dir / VECTORS_FILE)
        with open(index_dir / CHUNKS_FILE, encoding="utf-8") as f:
            chunks = [Chunk(**json.loads(line)) for line in f if line.strip()]
        logger.info("Index loaded: %d chunks, %s/%s", len(chunks), manifest["embedding_provider"],
                    manifest["embedding_model"])
        return cls(chunks, vectors, manifest)

    def search(self, query_vector: np.ndarray, top_k: int, source: str,
               filters: dict | None = None) -> list[tuple[Chunk, float]]:
        """Cosine top-k among chunks of `source` whose metadata matches every filter (value or list of values)."""
        filters = {k: v for k, v in (filters or {}).items() if v is not None}
        mask = np.array([c.source == source and all(
            (c.metadata.get(k) in v) if isinstance(v, (list, tuple, set)) else c.metadata.get(k) == v
            for k, v in filters.items()) for c in self.chunks])
        if not mask.any():
            return []
        idx = np.flatnonzero(mask)
        scores = self.vectors[idx] @ query_vector
        order = np.argsort(-scores)[:top_k]
        return [(self.chunks[idx[i]], float(scores[i])) for i in order]
