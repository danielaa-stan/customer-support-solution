# 03. MCP tools (A ↔ B contract)

Implemented by A (`/server`), called by B (`/agent`). Transport: stdio, FastMCP library (Python).

## Session context (security)

The LLM **never** passes `user_id` or chooses whose account to modify. The server operates only on the current session's user.

A system tool with the `sys_` prefix handles this. **B does not expose `sys_*` tools to the model.**

| Tool | Parameters | When B calls it |
|------------|-----------|-----------------|
| `sys_set_context` | `session_id: str`, `user_id: str`, `user_turn: int` | at the start of the chat and before each user turn (`user_turn` = user message counter, starting at 1) |

All tools below return `error.code = "NO_CONTEXT"` unless `sys_set_context` has been called.

## Unified response format

Every tool returns JSON in this form:

```json
{
  "ok": true,
  "status": "done",
  "data": { },
  "error": null,
  "needs_human": false,
  "audit_id": 128
}
```

| Field | Description |
|------|------|
| `ok` | `true` if the action was executed or proposed; `false` on denial or error |
| `status` | `done` · `pending_confirmation` · `denied` · `needs_human` · `error` |
| `data` | result (depends on the tool) or `null` |
| `error` | `null` or `{ "code": "...", "message": "...", "policy_ref": "refund-policy#2.1" }` |
| `needs_human` | `true` if the agent must hand the case over to a human (`escalate_to_human`) |
| `audit_id` | record ID in `audit_log` |

`error.message` is written so the agent can explain the reason to the customer. The agent cites `policy_ref` when present.

### Error codes

| Code | Meaning |
|-----|----------|
| `NO_CONTEXT` | `sys_set_context` has not been called |
| `NOT_FOUND` | object does not exist or belongs to another user |
| `INVALID_ARGUMENT` | invalid parameters |
| `POLICY_DENIED` | prohibited by policy (see `policy_ref`) |
| `NOT_ELIGIBLE` | offer is not available to this user |
| `ALREADY_DONE` | action has already been executed (idempotency) |
| `LIMIT_EXCEEDED` | automatic action limit exceeded → `needs_human = true` |
| `CONFIRMATION_REQUIRED` | user confirmation required |
| `CONFIRMATION_INVALID` | confirmation is not possible (no new user message, expired) |
| `INTERNAL` | unexpected error |

## Autonomy levels

| Level | Behavior |
|--------|-----------|
| `read` | read only, no side effects |
| `auto` | executed immediately if the rules allow it |
| `confirm` | server creates a `pending_action` and returns `pending_confirmation`; executed after `confirm_action` |
| `human_only` | server refuses with `needs_human = true`; followed by `escalate_to_human` |

**Two-step `confirm` flow:**

1. The agent calls, for example, `cancel_subscription(...)`. Response: `status = pending_confirmation`, `data.pending_action_id`, `data.summary`.
2. The agent explains exactly what will happen to the customer and requests explicit confirmation.
3. The customer replies. B increments `user_turn` and calls `sys_set_context`.
4. The agent calls `confirm_action(pending_action_id)`. The server executes the action only if `user_turn` is **greater than** `proposed_at_turn` (i.e. a new user message arrived after the proposal). Otherwise, `CONFIRMATION_INVALID`.
5. If the customer declines: `reject_action(pending_action_id)`.

## Tools visible to the model

### Read operations (`read`)

**`get_user_profile()`** → `data`:
```json
{
  "user": {"id": "u_...", "name": "...", "country": "UA", "is_student": false},
  "subscription": {"plan": "individual", "status": "active", "price_amount": 4.99,
                   "price_currency": "USD", "next_billing_date": "...", "tenure_months": 8,
                   "pending_plan": null, "paused_until": null, "cancel_at": null,
                   "discount_percent": 0},
  "usage": {"listening_hours_30d": 41.5, "last_active_at": "...", "devices_count": 2},
  "flags": {"retention_offer_used_in_cooldown": false}
}
```

**`get_payments(limit: int = 10)`** → `data.payments`: array of `{id, amount, currency, kind, status, charged_at, refunded_at, refund_reason}`, newest first. Also returns `data.duplicate_charge_candidates`: an array of `payment_id` pairs that appear to be duplicate charges (see rules in 04).

**`get_available_offers()`** → `data.offers`: array of `{code, title, description, details}` containing only offers the user **is currently eligible for** (the server checks eligibility itself). The agent does not invent offers.

### Actions

**`pause_subscription(months: int, reason_code: str)`** · `auto`
- `months` ranges from 1 to `PAUSE_MAX_MONTHS`. No charges during the pause.
- `data`: `{paused_until}`.

**`change_plan(new_plan: str, reason_code: str)`** · `auto`
- `new_plan`: `individual` | `duo` | `family` | `student` (`student` only if `is_student`).
- Upgrades take effect immediately; downgrades take effect at the next billing date (`pending_plan`).
- `data`: `{plan, pending_plan, effective, new_price_amount}`.

**`apply_retention_offer(offer_code: str, reason_code: str)`** · `auto`
- `offer_code` must come from `get_available_offers()`. Otherwise, `NOT_ELIGIBLE`.
- `data`: `{offer_code, discount_percent, discount_payments_left}` or `{free_months}`.

**`issue_refund(payment_id: str, reason_code: str, policy_ref: str)`** · `auto` / `human_only` depending on the rules
- Conditions and limits: [04-business-rules.md](04-business-rules.md).
- Success: `data`: `{payment_id, refunded_amount, currency}`.
- Payment outside the window: `POLICY_DENIED` (`refund-policy#2.1`).
- Amount above the automatic limit: `LIMIT_EXCEEDED`, `needs_human = true`.
- Repeated call for an already refunded payment: `ALREADY_DONE`.

**`cancel_subscription(reason_code: str, effective: str = "end_of_period")`** · `confirm`
- `effective`: `end_of_period` (default) or `immediate`.
- Response: `pending_confirmation`. After `confirm_action`: `data`: `{status, cancel_at}`.

**`confirm_action(pending_action_id: str)`** · executes the confirmed action (same result as the corresponding tool).

**`reject_action(pending_action_id: str)`** · rejects the pending action.

**`escalate_to_human(priority: str, category: str, summary: str, suggested_action: object | null)`** · `auto`
- Creates a ticket for a human agent. `summary`: a brief summary of the issue and what has already been done. `suggested_action`: `{tool, args, rationale, policy_ref}` or `null` (a "copilot recommendation" for the human).
- `data`: `{ticket_id}`.

## B's tools (not MCP): for reference

B registers these alongside MCP tools. The model sees them in the same way.

- `search_policy(query: str, top_k: int = 3)` → array of `{doc_id, section, title, text, policy_ref}`
- `find_similar_cases(query: str, top_k: int = 3)` → array of `{case_id, title, resolution, actions, outcome, policy_refs}`

## Audit log: what the server records automatically

For **every** call (including denials): `ts`, `session_id`, `user_id`, `tool`, `args`, `result_status`,
`error_code`, `autonomy_level`, `reason_code`, `policy_ref`, `actor`.
`confirm_action` adds a separate record and preserves the link through `args`.

## Idempotency

Repeating a call for an already executed action (same `payment_id`, same subscription state) does not execute it again;
it returns `ALREADY_DONE` without side effects.
