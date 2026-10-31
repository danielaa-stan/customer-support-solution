"""Deterministic SYNTHETIC rows for previewing the dashboard without a database.

Never written to any database. The UI labels this mode clearly.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

PLANS = ("individual", "duo", "family", "student")
OFFERS = (("discount_50_3m", "50% discount on the next three charges"), ("free_month_1", "One free month"))
SCENARIOS = [
    # intent, reason, resolutions (weighted)
    ("cancel_subscription", "price_too_high", ["retained", "retained", "canceled", "escalated"]),
    ("cancel_subscription", "low_usage", ["retained", "canceled", "canceled"]),
    ("cancel_subscription", "switching_competitor", ["canceled", "canceled", "retained"]),
    ("cancel_subscription", "temporary_break", ["retained", "retained"]),
    ("billing_issue", "double_charge", ["refunded", "refunded", "refunded", "escalated"]),
    ("refund_request", "billing_confusion", ["refunded", "resolved_auto", "escalated"]),
    ("technical_issue", "technical_problems", ["resolved_auto", "resolved_auto", "escalated", "abandoned"]),
    ("plan_change", "other", ["resolved_auto", "resolved_auto"]),
]


def generate(now: datetime | None = None, n: int = 60, seed: int = 7) -> tuple[list[dict], list[dict]]:
    rng = random.Random(seed)
    now = now or datetime.now(timezone.utc)
    conversations: list[dict] = []
    calls: list[dict] = []
    audit_id = 1
    for i in range(n):
        intent, reason, outcomes = rng.choice(SCENARIOS)
        resolution = rng.choice(outcomes)
        start = now - timedelta(days=rng.randint(0, 13), hours=rng.randint(0, 20), minutes=rng.randint(0, 59))
        duration = rng.randint(60, 600)
        sid = f"sample-{i:03d}"
        s0 = rng.choice([-2, -1, -1, 0])
        s1 = max(-2, min(2, s0 + (rng.choice([1, 1, 2]) if resolution in ("retained", "refunded", "resolved_auto") else rng.choice([-1, 0, 0]))))
        conversations.append({
            "session_id": sid, "user_id": f"u_{rng.randint(100, 140)}", "started_at": start,
            "ended_at": start + timedelta(seconds=duration), "duration_seconds": duration,
            "plan_code": rng.choice(PLANS), "intent": intent, "reason": reason, "resolution": resolution,
            "sentiment_start": s0, "sentiment_end": s1,
            "churn_risk": round(rng.uniform(0.5, 0.95) if resolution == "canceled" else rng.uniform(0.05, 0.6), 4),
            "quality_correctness": rng.choice([4, 5, 5, 3]) if rng.random() > 0.1 else None,
            "quality_policy_compliance": rng.choice([5, 5, 4]),
            "quality_tone": rng.choice([4, 5, 5]),
            "quality_resolved": resolution not in ("escalated", "abandoned"),
            "kb_gap": rng.random() < 0.08,
            "summary": f"Synthetic {intent.replace('_', ' ')} conversation ({reason.replace('_', ' ')}); outcome {resolution}.",
        })

        def call(tool, status="done", autonomy="read", actor="agent", **extra):
            nonlocal audit_id
            row = {"audit_id": audit_id, "session_id": sid, "occurred_at": start + timedelta(seconds=audit_id % 50 + 5),
                   "tool_name": tool, "result_status": status, "autonomy_level": autonomy, "actor": actor,
                   "error_code": None, "offer_code": None, "offer_title": None, "refunded_amount": None,
                   "currency": None, "reason": None, "policy_ref": None}
            row.update(extra)
            calls.append(row)
            audit_id += 1

        call("get_user_profile")
        call("search_policy", policy_ref="agent-conduct#1.3")
        if resolution == "retained":
            code, title = rng.choice(OFFERS)
            call("apply_retention_offer", autonomy="confirm", offer_code=code, offer_title=title, reason=reason)
        elif resolution == "refunded":
            amount = rng.choice([4.99, 6.49, 7.99])
            call("issue_refund", autonomy="auto", refunded_amount=amount, currency="USD",
                 policy_ref="refund-policy#2.2", reason=reason)
        elif resolution == "canceled":
            call("cancel_subscription", autonomy="confirm", reason=reason)
        elif resolution == "escalated":
            call("escalate_to_human", status="needs_human", autonomy="human_only")
    return conversations, calls
