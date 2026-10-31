"""Dashboard aggregation following analytics/README.md "Dashboard aggregation".

Pure functions over the two flat row lists from source.py (conversations, tool calls).
The two fact tables are aggregated separately and never joined row-by-row.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import timezone

RESOLVED_WITHOUT_ESCALATION = ("resolved_auto", "retained", "canceled", "refunded")
QUALITY_FIELDS = (
    ("quality_correctness", "Correctness"),
    ("quality_policy_compliance", "Policy compliance"),
    ("quality_tone", "Tone"),
)


def _rate(part: int, total: int) -> float | None:
    return part / total if total else None


def outcomes(conversations: list[dict]) -> dict:
    total = len(conversations)
    counts = Counter(c["resolution"] for c in conversations)
    resolved = sum(counts[k] for k in RESOLVED_WITHOUT_ESCALATION)
    return {
        "total": total,
        "counts": dict(counts),
        "resolved_rate": _rate(resolved, total),
        "escalated_rate": _rate(counts["escalated"], total),
        "abandoned_rate": _rate(counts["abandoned"], total),
        "retained": counts["retained"],
    }


def cancellation_reasons(conversations: list[dict]) -> list[dict]:
    """Conversation-level intent+reason pairs for cancellation-related intents."""
    pairs = Counter(
        (c["intent"], c["reason"])
        for c in conversations
        if c["intent"] in ("cancel_subscription", "refund_request", "billing_issue")
    )
    return [
        {"intent": i, "reason": r, "count": n}
        for (i, r), n in sorted(pairs.items(), key=lambda kv: -kv[1])
    ]


def retention_offers(tool_calls: list[dict]) -> list[dict]:
    counts: Counter = Counter()
    titles: dict[str, str] = {}
    for t in tool_calls:
        if (
            t["tool_name"] == "apply_retention_offer"
            and t["result_status"] == "done"
            and t.get("offer_code")
        ):
            counts[t["offer_code"]] += 1
            titles[t["offer_code"]] = t.get("offer_title") or t["offer_code"]
    return [
        {"offer": titles[k], "accepted": n} for k, n in counts.most_common()
    ]


def auto_refunds(tool_calls: list[dict]) -> dict:
    """Verified automatic refunds per currency; unverified refunds are 'incomplete', not zero."""
    totals: dict[str, float] = defaultdict(float)
    count = 0
    incomplete = 0
    for t in tool_calls:
        if (
            t["tool_name"] != "issue_refund"
            or t["result_status"] != "done"
            or t["autonomy_level"] != "auto"
            or t["actor"] != "agent"
        ):
            continue
        if t.get("refunded_amount") is None:
            incomplete += 1
            continue
        totals[t["currency"]] += float(t["refunded_amount"])
        count += 1
    return {"totals": dict(totals), "count": count, "incomplete": incomplete}


def quality(conversations: list[dict]) -> list[dict]:
    rows = []
    for field, label in QUALITY_FIELDS:
        values = [c[field] for c in conversations if c.get(field) is not None]
        rows.append(
            {
                "metric": label,
                "average": sum(values) / len(values) if values else None,
                "assessed": len(values),
            }
        )
    return rows


def sentiment(conversations: list[dict]) -> dict:
    pairs = [
        (c["sentiment_start"], c["sentiment_end"])
        for c in conversations
        if c.get("sentiment_start") is not None and c.get("sentiment_end") is not None
    ]
    n = len(pairs)
    return {
        "assessed": n,
        "avg_start": sum(p[0] for p in pairs) / n if n else None,
        "avg_end": sum(p[1] for p in pairs) / n if n else None,
        "improved": sum(1 for a, b in pairs if b > a),
        "worsened": sum(1 for a, b in pairs if b < a),
    }


def churn_risk(conversations: list[dict]) -> dict:
    values = [float(c["churn_risk"]) for c in conversations if c.get("churn_risk") is not None]
    high = sum(1 for v in values if v >= 0.7)
    return {
        "assessed": len(values),
        "average": sum(values) / len(values) if values else None,
        "high_risk": high,
    }


def daily_volume(conversations: list[dict]) -> list[dict]:
    per_day: dict = defaultdict(lambda: Counter())
    for c in conversations:
        day = c["started_at"].astimezone(timezone.utc).date()
        per_day[day][c["resolution"]] += 1
    return [
        {"day": d, "conversations": sum(cnt.values()), **cnt}
        for d, cnt in sorted(per_day.items())
    ]


def tool_usage(tool_calls: list[dict]) -> list[dict]:
    stats: dict = defaultdict(lambda: Counter())
    for t in tool_calls:
        stats[t["tool_name"]][t["result_status"]] += 1
    return [
        {"tool": name, "calls": sum(c.values()), **dict(c)}
        for name, c in sorted(stats.items(), key=lambda kv: -sum(kv[1].values()))
    ]


def policy_citations(tool_calls: list[dict]) -> list[dict]:
    counts = Counter(t["policy_ref"] for t in tool_calls if t.get("policy_ref"))
    return [{"policy": k, "calls": n} for k, n in counts.most_common()]


def knowledge_gaps(conversations: list[dict]) -> dict:
    gaps = [c for c in conversations if c.get("kb_gap")]
    return {"count": len(gaps), "sessions": gaps}


def session_tool_calls(tool_calls: list[dict], session_id: str) -> list[dict]:
    """Drill-down: every tool-call row for one session, including failures and proposals."""
    return [t for t in tool_calls if t["session_id"] == session_id]
