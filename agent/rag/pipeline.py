"""Wire the RAG steps together: build the index (offline) and load a retriever (at runtime)."""
from __future__ import annotations

import logging

from agent.rag.chunking import chunk_cases, chunk_policies
from agent.rag.embeddings import Embedder, GeminiEmbedder, RateLimit, TfidfEmbedder
from agent.rag.index import VectorIndex
from agent.rag.loader import load_cases, load_policies
from agent.rag.retriever import Retriever
from agent.settings import Settings

logger = logging.getLogger(__name__)


def make_embedder(settings: Settings, for_loading: bool = False) -> Embedder:
    rag = settings.rag
    if rag.embedding_provider == "gemini":
        return GeminiEmbedder(rag.embedding_model, settings.gemini_api_key, settings.llm.base_url,
                              rag.embedding_batch_size, settings.llm.max_retries, settings.llm.retry_backoff_s,
                              RateLimit(rag.embedding_texts_per_minute, rag.rate_limit_max_retries,
                                        rag.rate_limit_wait_s))
    if rag.embedding_provider == "tfidf":
        return TfidfEmbedder.load(rag.index_dir) if for_loading else TfidfEmbedder()
    raise ValueError(f"Unknown embedding_provider: {rag.embedding_provider}")


def build_index(settings: Settings, embedder: Embedder | None = None) -> VectorIndex:
    rag = settings.rag
    chunks = (chunk_policies(load_policies(rag.policies_dir), rag.max_chunk_chars, rag.chunk_overlap_sentences)
              + chunk_cases(load_cases(rag.cases_file)))
    embedder = embedder or make_embedder(settings)
    texts = [c.text for c in chunks]
    embedder.fit(texts)
    logger.info("Embedding %d chunks with %s/%s", len(chunks), embedder.provider, embedder.model)
    index = VectorIndex.build(chunks, embedder.embed(texts), embedder.provider, embedder.model)
    index.save(rag.index_dir)
    embedder.save(rag.index_dir)
    return index


def load_retriever(settings: Settings, embedder: Embedder | None = None) -> Retriever:
    rag = settings.rag
    index = VectorIndex.load(rag.index_dir)
    embedder = embedder or make_embedder(settings, for_loading=True)
    if embedder.provider not in rag.min_score:
        raise ValueError(f"settings.toml [rag] min_score has no value for '{embedder.provider}'")
    return Retriever(index, embedder, rag.policy_top_k, rag.case_top_k, rag.min_score[embedder.provider])
