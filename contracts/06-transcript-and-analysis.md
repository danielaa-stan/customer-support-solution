# 06. Conversation transcript and analysis result

## Shared enums

`intent` (primary intent):
`cancel_subscription`, `billing_issue`, `refund_request`, `plan_change`, `technical_issue`, `account_access`, `other`

`reason_code` (underlying reason; used by both A's tools and C's analyzer):
`price_too_high`, `low_usage`, `technical_problems`, `switching_competitor`, `double_charge`,
`billing_confusion`, `temporary_break`, `other`, `unknown`

`resolution` (conversation outcome):
`resolved_auto` (resolved by AI independently), `retained` (customer retained), `canceled`, `refunded`, `escalated`, `abandoned`

## Transcript: `runtime/transcripts/{session_id}.json` (written by B, read by C)

B writes the file when the conversation ends (user left, issue resolved, escalation). The file may also be overwritten during the conversation.

```json
{
  "session_id": "ses_20261031_0001",
  "user_id": "u_demo_family",
  "started_at": "2026-10-31T12:00:05Z",
  "ended_at": "2026-10-31T12:04:41Z",
  "end_reason": "resolved_by_agent",
  "messages": [
    {"seq": 1, "role": "user", "ts": "2026-10-31T12:00:05Z",
     "content": "It has become too expensive. I want to cancel my subscription."},
    {"seq": 2, "role": "assistant", "ts": "2026-10-31T12:00:09Z",
     "content": "I understand. Let me check your account ...",
     "tool_calls": [{"name": "get_user_profile", "args": {}}]},
    {"seq": 3, "role": "tool", "ts": "2026-10-31T12:00:10Z",
     "name": "get_user_profile", "content": {"ok": true, "status": "done"}}
  ]
}
```

Rules:

- `role`: `user` | `assistant` | `tool` | `system`.
- `end_reason`: `resolved_by_agent` | `escalated` | `user_left`.
- `seq` starts at 1 and increases. The `content` of `tool` messages contains the actual tool response (large fields may be shortened).
- C obtains executed actions **from `audit_log`, not from the transcript** (the source of truth for executed actions). The transcript provides the conversation text.

## Analysis result: `analysis` table in `runtime/analytics.db` (owned by C)

One row per session. B and A do not use this table.

| Field | Type | Description |
|------|-----|------|
| `session_id` | TEXT PK | |
| `user_id` | TEXT | |
| `primary_intent` | TEXT | enum `intent` |
| `underlying_reason` | TEXT | enum `reason_code` (underlying reason, which may differ from what was stated) |
| `sentiment_start` | INTEGER | −2 (very negative) … +2 (very positive) |
| `sentiment_end` | INTEGER | same as above |
| `churn_risk` | REAL | 0.0 – 1.0 after the conversation |
| `resolution` | TEXT | enum `resolution` |
| `actions_json` | TEXT | list of executed actions (from `audit_log`) |
| `policy_refs_json` | TEXT | policies used |
| `quality_json` | TEXT | AI response quality score: `{"correctness":1-5,"policy_compliance":1-5,"tone":1-5,"resolved":true}` |
| `kb_gap` | INTEGER | 1 if the agent found no answer in the knowledge base |
| `summary` | TEXT | 1–2 sentences for the dashboard |
| `analyzed_at` | TEXT | ISO 8601 |

## What the dashboard shows (minimum)

1. Top cancellation reasons (`underlying_reason`).
2. Proportion of conversations resolved independently by AI versus escalated.
3. Number of customers retained and which offer worked.
4. Number and total amount of automatic refunds.
5. Average AI response quality and knowledge base gaps (`kb_gap`).
6. AI action log (from `audit_log`) for the selected conversation.
