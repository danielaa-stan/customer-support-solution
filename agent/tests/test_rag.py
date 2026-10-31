"""RAG pipeline tests with the offline TF-IDF embedder and a tiny KB in tests/fixtures/kb."""
from dataclasses import replace
from pathlib import Path

import pytest

from agent.rag.chunking import chunk_cases, chunk_policies, split_sentences
from agent.rag.cleaning import clean_text
from agent.rag.loader import load_cases, load_policies, parse_front_matter
from agent.rag.pipeline import build_index, load_retriever
from agent.tools.rag_provider import RAGToolProvider

KB = Path(__file__).resolve().parent / "fixtures" / "kb"


@pytest.fixture()
def rag_settings(settings, tmp_path):
    rag = replace(settings.rag, policies_dir=KB / "policies", cases_file=KB / "cases.json",
                  index_dir=tmp_path / "rag", embedding_provider="tfidf", embedding_model="tfidf-1-2gram")
    return replace(settings, rag=rag)


@pytest.fixture()
def retriever(rag_settings):
    build_index(rag_settings)
    return load_retriever(rag_settings)


def test_front_matter_and_sections_are_parsed():
    sections = load_policies(KB / "policies")
    refs = [s.policy_ref for s in sections]
    assert "refund-policy#2.2" in refs and "retention-rules#1.3" in refs
    assert parse_front_matter("---\ndoc_id: x\n---\nbody")[0] == {"doc_id": "x"}


def test_policy_chunks_carry_citation_metadata():
    chunk = next(c for c in chunk_policies(load_policies(KB / "policies"), 1200, 1)
                 if c.metadata["policy_ref"] == "refund-policy#2.2")
    assert chunk.metadata["doc_id"] == "refund-policy" and chunk.metadata["section"] == "2.2"
    assert "Duplicate charge" in chunk.text


def test_long_section_is_split_with_overlap():
    parts = split_sentences("One. Two. Three. Four.", max_chars=10, overlap=1)
    assert len(parts) > 1 and parts[1].startswith(parts[0].split()[-1])


def test_case_chunk_uses_title_message_and_summary():
    chunk = chunk_cases(load_cases(KB / "cases.json"))[1]
    assert "Charged twice" in chunk.text and "refunded the second" in chunk.text
    assert chunk.metadata["reason"] == "double_charge"


def test_cleaning():
    assert clean_text("**Bold**  text\n\n\n\n[link](http://x)") == "Bold text\n\nlink"


def test_search_policy_finds_duplicate_rule(retriever):
    r = retriever.search_policy("I was charged twice, duplicate payment")
    assert r.results[0]["policy_ref"] == "refund-policy#2.2" and not r.kb_gap


def test_metadata_filter_by_doc(retriever):
    r = retriever.search_policy("discount offer", doc_id="retention-rules")
    assert r.results and all(x["doc_id"] == "retention-rules" for x in r.results)


def test_similar_cases_with_reason_filter(retriever):
    r = retriever.find_similar_cases("too expensive", reason="price_too_high")
    assert [x["case_id"] for x in r.results] == ["case_0001"]


def test_unrelated_query_is_a_kb_gap(retriever):
    assert retriever.search_policy("podcast lyrics karaoke").kb_gap


def test_index_built_with_other_embedder_is_rejected(rag_settings):
    build_index(rag_settings)
    other = replace(rag_settings, rag=replace(rag_settings.rag, embedding_provider="gemini",
                                              embedding_model="gemini-embedding-001"))
    with pytest.raises(ValueError, match="Rebuild"):
        load_retriever(other)


def test_rag_tools_return_contract_envelope(retriever, rag_settings):
    provider = RAGToolProvider(retriever, rag_settings.rag.tools_file)
    assert {t.name for t in provider.list_tools()} == {"search_policy", "find_similar_cases"}
    res = provider.call("search_policy", {"query": "duplicate charge"})
    assert res.ok and res.status == "done" and res.data["results"][0]["policy_ref"] == "refund-policy#2.2"
    assert provider.call("search_policy", {"query": " "}).error["code"] == "INVALID_ARGUMENT"
