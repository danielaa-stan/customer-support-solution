"""Step 6: the two retrieval operations the agent uses, in the contracts/03 output format."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from agent.rag.embeddings import Embedder
from agent.rag.index import VectorIndex

logger = logging.getLogger(__name__)
MAX_TOP_K = 5


@dataclass
class RetrievalResult:
    results: list[dict]
    kb_gap: bool                 # nothing relevant found (score below min_score)
    best_score: float | None


class Retriever:
    def __init__(self, index: VectorIndex, embedder: Embedder, policy_top_k: int, case_top_k: int,
                 min_score: float):
        if index.manifest["embedding_provider"] != embedder.provider or \
                index.manifest["embedding_model"] != embedder.model:
            raise ValueError(f"Index was built with {index.manifest['embedding_provider']}/"
                             f"{index.manifest['embedding_model']}, settings use {embedder.provider}/{embedder.model}. "
                             "Rebuild: python -m agent.scripts.build_index")
        self.index, self.embedder = index, embedder
        self.policy_top_k, self.case_top_k, self.min_score = policy_top_k, case_top_k, min_score

    def search_policy(self, query: str, top_k: int | None = None, doc_id: str | None = None) -> RetrievalResult:
        hits = self._search(query, "policy", top_k or self.policy_top_k, {"doc_id": doc_id})
        results = [{"doc_id": c.metadata["doc_id"], "section": c.metadata["section"], "title": c.metadata["title"],
                    "text": c.metadata["text"], "policy_ref": c.metadata["policy_ref"], "score": round(s, 3)}
                   for c, s in hits]
        return self._result(results, hits, query, "policy")

    def find_similar_cases(self, query: str, top_k: int | None = None, reason: str | None = None) -> RetrievalResult:
        hits = self._search(query, "case", top_k or self.case_top_k, {"reason": reason})
        results = [{"case_id": c.metadata["case_id"], "title": c.metadata["title"],
                    "resolution": c.metadata["resolution"], "actions": c.metadata["actions"],
                    "outcome": c.metadata["resolution"], "policy_refs": c.metadata["policy_refs"],
                    "score": round(s, 3)} for c, s in hits]
        return self._result(results, hits, query, "case")

    # ------------------------------------------------------------------ internals
    def _search(self, query: str, source: str, top_k: int, filters: dict):
        top_k = max(1, min(int(top_k), MAX_TOP_K))
        vector = self.embedder.embed([query])[0]
        hits = self.index.search(vector, top_k, source, filters)
        return [(c, s) for c, s in hits if s >= self.min_score]

    def _result(self, results: list[dict], hits, query: str, source: str) -> RetrievalResult:
        best = hits[0][1] if hits else None
        gap = not results
        logger.info("RAG %s '%s': %d results, best=%s, kb_gap=%s", source, query, len(results),
                    f"{best:.3f}" if best is not None else None, gap)
        return RetrievalResult(results, gap, best)
