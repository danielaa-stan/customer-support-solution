"""Evaluate the RAG: retrieval metrics, and optionally answers with vs without retrieval.

Run from the repo root:
  python -m agent.scripts.eval_rag                 retrieval metrics only (cheap: ~20 embedding calls)
  python -m agent.scripts.eval_rag --answers 5     + answers with vs without RAG for 5 questions (15 LLM calls)
Report: runtime/eval/rag_eval.json (+ summary in the log).
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import asdict
from pathlib import Path

from agent.eval.rag_eval import evaluate_answers, evaluate_retrieval, suggested_min_score
from agent.llm import LLMClient
from agent.logging_config import setup_logging
from agent.prompts import PromptLibrary
from agent.rag.pipeline import load_retriever
from agent.settings import load_settings

logger = logging.getLogger("eval_rag")
EVAL_SET = Path(__file__).resolve().parents[1] / "config" / "eval_rag.json"
REPORT = Path("runtime/eval/rag_eval.json")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--answers", type=int, default=0, help="questions to compare with vs without RAG")
    args = parser.parse_args()

    settings = load_settings()
    setup_logging(settings.logging)
    data = json.loads(EVAL_SET.read_text(encoding="utf-8"))
    retriever = load_retriever(settings)
    k = settings.rag.policy_top_k

    r = evaluate_retrieval(retriever, data["in_scope"], data["out_of_scope"], k)
    report = {"embedding": retriever.index.manifest["embedding_model"], "min_score": retriever.min_score,
              "retrieval": asdict(r), "suggested_min_score": suggested_min_score(r)}
    logger.info("RETRIEVAL (%d in-scope, %d out-of-scope questions, k=%d)", len(data["in_scope"]),
                len(data["out_of_scope"]), k)
    logger.info("  hit@1 = %.0f%%   recall@%d = %.0f%%   MRR = %.2f", r.hit_at_1 * 100, k, r.recall_at_k * 100, r.mrr)
    logger.info("  missing context detected (kb_gap on out-of-scope) = %.0f%%   false kb_gap on in-scope = %.0f%%",
                r.gap_detection_rate * 100, r.false_gap_rate * 100)
    logger.info("  best score in-scope: min %.2f / max %.2f;  out-of-scope: min %.2f / max %.2f;  min_score = %.2f",
                min(r.in_scope_best_scores), max(r.in_scope_best_scores), min(r.out_of_scope_best_scores),
                max(r.out_of_scope_best_scores), retriever.min_score)
    if report["suggested_min_score"] is not None:
        logger.info("  suggested min_score = %.3f (separates in-scope from out-of-scope)", report["suggested_min_score"])
    for d in r.details:
        if d["rank"] != 1:
            logger.info("  miss: %r expected %s got %s", d["question"], d["expected"], d["retrieved"])

    if args.answers:
        prompts = PromptLibrary(settings.prompts.dir)
        a = evaluate_answers(retriever, LLMClient.from_settings(settings), prompts, data["in_scope"], args.answers, k)
        report["answers"] = a
        logger.info("ANSWERS (%d questions, judged against the reference policy)", args.answers)
        for key in ("without_rag", "with_rag"):
            s = a[key]
            logger.info("  %-12s accuracy %.0f%%   hallucination rate %.0f%%   cites policy %.0f%%", key,
                        s["accuracy"] * 100, s["hallucination_rate"] * 100, s["citation_rate"] * 100)

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Report saved to %s", REPORT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
