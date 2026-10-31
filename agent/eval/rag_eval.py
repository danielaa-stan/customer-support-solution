"""RAG evaluation: retrieval quality and answer quality with vs without retrieval.

Retrieval (embeddings only):  hit@1, recall@k, MRR, missing-context detection on out-of-scope questions,
                              similarity score distribution (to calibrate min_score).
Answers (LLM):                for each question, one answer without context and one with retrieved policies;
                              an LLM judge compares both with the reference policy text.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field

from agent.llm import LLMClient
from agent.prompts import PromptLibrary
from agent.rag.retriever import Retriever

logger = logging.getLogger(__name__)


@dataclass
class RetrievalReport:
    hit_at_1: float
    recall_at_k: float
    mrr: float
    k: int
    gap_detection_rate: float          # out-of-scope questions correctly flagged as kb_gap
    false_gap_rate: float              # in-scope questions wrongly flagged as kb_gap
    in_scope_best_scores: list[float]
    out_of_scope_best_scores: list[float]
    details: list[dict] = field(default_factory=list)


def evaluate_retrieval(retriever: Retriever, in_scope: list[dict], out_of_scope: list[str], k: int) -> RetrievalReport:
    hits1 = hitsk = rr = false_gaps = 0
    in_scores, details = [], []
    for case in in_scope:
        raw = retriever.index.search(retriever.embedder.embed([case["question"]])[0], k, "policy")
        refs = [c.metadata["policy_ref"] for c, _ in raw]
        best = raw[0][1] if raw else 0.0
        in_scores.append(round(best, 3))
        rank = refs.index(case["expected"]) + 1 if case["expected"] in refs else None
        hits1 += rank == 1
        hitsk += rank is not None
        rr += 1 / rank if rank else 0
        false_gaps += best < retriever.min_score
        details.append({"question": case["question"], "expected": case["expected"], "retrieved": refs,
                        "rank": rank, "best_score": round(best, 3)})
    out_scores, gaps = [], 0
    for q in out_of_scope:
        raw = retriever.index.search(retriever.embedder.embed([q])[0], 1, "policy")
        best = raw[0][1] if raw else 0.0
        out_scores.append(round(best, 3))
        gaps += best < retriever.min_score
    n, m = len(in_scope), max(1, len(out_of_scope))
    return RetrievalReport(hits1 / n, hitsk / n, rr / n, k, gaps / m, false_gaps / n, in_scores, out_scores, details)


def suggested_min_score(report: RetrievalReport) -> float | None:
    """Midpoint between the highest out-of-scope score and the lowest in-scope score, if they separate."""
    if not report.out_of_scope_best_scores or not report.in_scope_best_scores:
        return None
    hi_out, lo_in = max(report.out_of_scope_best_scores), min(report.in_scope_best_scores)
    return round((hi_out + lo_in) / 2, 3) if lo_in > hi_out else None


def _judge(llm: LLMClient, prompts: PromptLibrary, question: str, answer: str, ref: str, reference: str) -> dict:
    text = prompts.get("eval_judge").format(policy_ref=ref, reference=reference, question=question, answer=answer)
    reply = llm.chat([{"role": "user", "content": text}])
    m = re.search(r"\{.*\}", reply.content, re.S)
    try:
        return json.loads(m.group(0)) if m else {}
    except json.JSONDecodeError:
        return {}


def evaluate_answers(retriever: Retriever, llm: LLMClient, prompts: PromptLibrary, in_scope: list[dict],
                     limit: int, k: int) -> dict:
    by_ref = {c.metadata["policy_ref"]: c.metadata["text"] for c in retriever.index.chunks if c.source == "policy"}
    rows = []
    for case in in_scope[:limit]:
        q, ref = case["question"], case["expected"]
        plain = llm.chat([{"role": "system", "content": prompts.get("eval_answer_without_rag")},
                          {"role": "user", "content": q}]).content
        hits = retriever.search_policy(q, top_k=k).results
        context = "\n\n".join(f"[{h['policy_ref']}] {h['title']}: {h['text']}" for h in hits)
        grounded = llm.chat([{"role": "system", "content": prompts.get("eval_answer_with_rag").format(context=context)},
                             {"role": "user", "content": q}]).content
        row = {"question": q, "expected": ref,
               "without_rag": {"answer": plain, **_judge(llm, prompts, q, plain, ref, by_ref[ref])},
               "with_rag": {"answer": grounded, **_judge(llm, prompts, q, grounded, ref, by_ref[ref])}}
        logger.info("[%s] without RAG: %s | with RAG: %s", ref,
                    {k: row["without_rag"].get(k) for k in ("correct", "hallucination", "cites_policy")},
                    {k: row["with_rag"].get(k) for k in ("correct", "hallucination", "cites_policy")})
        rows.append(row)

    def summary(key: str) -> dict:
        judged = [r[key] for r in rows if "correct" in r[key]]
        n = max(1, len(judged))
        return {"answers": len(judged),
                "accuracy": round(sum(int(j.get("correct", 0)) for j in judged) / (2 * n), 3),
                "hallucination_rate": round(sum(bool(j.get("hallucination")) for j in judged) / n, 3),
                "citation_rate": round(sum(bool(j.get("cites_policy")) for j in judged) / n, 3)}
    return {"without_rag": summary("without_rag"), "with_rag": summary("with_rag"), "rows": rows}
