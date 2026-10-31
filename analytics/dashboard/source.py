"""Data access: two flat reads (one per fact table); all aggregation lives in metrics.py."""
from __future__ import annotations

import os
from typing import Any

CONVERSATIONS_SQL = """
SELECT f.session_id, c.user_id, f.started_at, f.ended_at, f.duration_seconds,
       p.plan_code, i.intent_code AS intent, r.reason_code AS reason,
       s.resolution_code AS resolution, f.sentiment_start, f.sentiment_end, f.churn_risk,
       f.quality_correctness, f.quality_policy_compliance, f.quality_tone,
       f.quality_resolved, f.kb_gap, f.summary
FROM fact_conversation f
JOIN dim_customer c ON c.customer_key = f.customer_key
JOIN dim_plan p ON p.plan_key = f.plan_key
JOIN dim_intent i ON i.intent_key = f.intent_key
JOIN dim_reason r ON r.reason_key = f.reason_key
JOIN dim_resolution s ON s.resolution_key = f.resolution_key
WHERE f.started_at >= %(since)s
ORDER BY f.started_at DESC
"""

TOOL_CALLS_SQL = """
SELECT t.audit_id, t.session_id, t.occurred_at, d.tool_name, t.result_status,
       t.autonomy_level, t.actor, t.error_code, o.offer_code, o.title AS offer_title,
       t.refunded_amount, t.currency, r.reason_code AS reason, p.policy_ref
FROM fact_tool_call t
JOIN dim_tool d ON d.tool_key = t.tool_key
LEFT JOIN dim_offer o ON o.offer_key = t.offer_key
LEFT JOIN dim_reason r ON r.reason_key = t.reason_key
LEFT JOIN dim_policy p ON p.policy_key = t.policy_key
WHERE t.occurred_at >= %(since)s
ORDER BY t.occurred_at
"""


def load_postgres(since: Any, url: str | None = None) -> tuple[list[dict], list[dict]]:
    """Read both fact tables. `since` is a timezone-aware datetime (window start)."""
    from analytics.db import connect

    url = url or os.environ["ANALYTICS_DATABASE_URL"]
    with connect(url) as conn:
        conversations = conn.execute(CONVERSATIONS_SQL, {"since": since}).fetchall()
        tool_calls = conn.execute(TOOL_CALLS_SQL, {"since": since}).fetchall()
    return conversations, tool_calls
